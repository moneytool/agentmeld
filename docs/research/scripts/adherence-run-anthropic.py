"""Does rule adherence degrade as the rule set grows?

Holds the 10 checkable rules constant and pads with filler, so the only variable
is how much other material surrounds them. Rule order is shuffled per run and
recorded, so position can be examined separately.
"""
import json, os, pathlib, random, sys, time
from concurrent.futures import ThreadPoolExecutor
import threading
LOCK = threading.Lock()
sys.path.insert(0, "/tmp/adherence")
from rules import CHECKS, FILLER
import anthropic

MODEL = "claude-opus-5"
SIZES = [10, 40, 120]
REPS  = 3
OUT   = pathlib.Path(os.environ.get("ADH_OUT", "/tmp/adherence/results_v2.json"))

TASKS = [
  ("config-loader", "Write a Python module that loads a JSON config file from disk and returns a dictionary, with a default path and error handling."),
  ("csv-summary",   "Write a Python module that reads a CSV of sales rows and returns total revenue per region."),
  ("retry",         "Write a Python module providing a retry decorator with exponential backoff."),
  ("log-parser",    "Write a Python module that parses a log file and counts entries by severity level."),
  ("cache",         "Write a Python module implementing a small on-disk key/value cache."),
]

def filler(n):
    out = []
    i = 0
    while len(out) < n:
        base = FILLER[i % len(FILLER)]
        out.append(base if i < len(FILLER) else f"{base} (applies to module {i//len(FILLER)}.)")
        i += 1
    return out[:n]

def build_rules(size, rng):
    core = [(k, v["text"]) for k, v in CHECKS.items()]
    pad  = [(f"filler-{i}", t) for i, t in enumerate(filler(max(0, size - len(core))))]
    rules = core + pad
    rng.shuffle(rules)
    positions = {k: i for i, (k, _) in enumerate(rules)}
    body = "\n".join(f"- {t}" for _, t in rules)
    return body, positions

def extract_code(text):
    if "```" not in text: return text
    parts = text.split("```")
    for p in parts[1:]:
        body = p.split("\n", 1)[-1] if p.split("\n", 1)[0].strip() in ("python", "py", "") else p
        if "def " in body or "import " in body:
            return body.rsplit("```", 1)[0]
    return text

def one(client, size, task_id, task, rep):
    rng = random.Random(f"{size}-{task_id}-{rep}")
    body, positions = build_rules(size, rng)
    system = ("You are contributing to an existing Python codebase. "
              "Follow every one of these project rules exactly:\n\n" + body)
    try:
        with client.messages.stream(
            model=MODEL, max_tokens=8000,
            output_config={"effort": "medium"},
            system=[{"type": "text", "text": system,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": task}],
        ) as s_:
            msg = s_.get_final_message()
    except Exception as e:
        print(f"  ERROR {size}/{task_id}/{rep}: {e}", file=sys.stderr)
        return None
    text = "".join(b.text for b in msg.content if b.type == "text")
    code = extract_code(text)
    compliance = {}
    for k, v in CHECKS.items():
        try: compliance[k] = v["fn"](code)
        except Exception: compliance[k] = None
    ok = sum(1 for v in compliance.values() if v is True)
    na = sum(1 for v in compliance.values() if v is None)
    print(f"  size={size:3d} {task_id:14s} rep{rep}  pass={ok}/{10-na} (n/a {na})", file=sys.stderr)
    return {"size": size, "task": task_id, "rep": rep, "compliance": compliance,
            "positions": positions, "in_tok": msg.usage.input_tokens,
            "cache_read": getattr(msg.usage, "cache_read_input_tokens", 0),
            "out_tok": msg.usage.output_tokens, "code_len": len(code), "code": code}


def main():
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    results = []
    if OUT.exists():
        results = json.loads(OUT.read_text())
    done = {(r["size"], r["task"], r["rep"]) for r in results}

    todo = [(size, tid, t, rep) for size in SIZES for tid, t in TASKS
            for rep in range(REPS) if (size, tid, rep) not in done]
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(one, client, s_, tid, t, rep) for s_, tid, t, rep in todo]
        for f in futs:
            r = f.result()
            if r:
                with LOCK:
                    cur = json.loads(OUT.read_text()) if OUT.exists() else []
                    seen = {(x["size"], x["task"], x["rep"]) for x in cur}
                    if (r["size"], r["task"], r["rep"]) not in seen:
                        cur.append(r)
                    OUT.write_text(json.dumps(cur, indent=1))
                    results = cur
    print(f"  DONE {len(results)} runs", file=sys.stderr)


def _unused():
    for size in SIZES:
        for task_id, task in TASKS:
            for rep in range(REPS):
                if False:
                    continue
                rng = random.Random(f"{size}-{task_id}-{rep}")
                body, positions = build_rules(size, rng)
                system = ("You are contributing to an existing Python codebase. "
                          "Follow every one of these project rules exactly:\n\n" + body)
                try:
                    with client.messages.stream(
                        model=MODEL, max_tokens=8000,
                        output_config={"effort": "medium"},
                        system=[{"type": "text", "text": system,
                                 "cache_control": {"type": "ephemeral"}}],
                        messages=[{"role": "user", "content": task}],
                    ) as s:
                        msg = s.get_final_message()
                except Exception as e:
                    print(f"  ERROR {size}/{task_id}/{rep}: {e}", file=sys.stderr)
                    continue
                text = "".join(b.text for b in msg.content if b.type == "text")
                code = extract_code(text)
                compliance = {}
                for k, v in CHECKS.items():
                    try: compliance[k] = v["fn"](code)
                    except Exception: compliance[k] = None
                results.append({
                    "size": size, "task": task_id, "rep": rep,
                    "compliance": compliance, "positions": positions,
                    "in_tok": msg.usage.input_tokens,
                    "cache_read": getattr(msg.usage, "cache_read_input_tokens", 0),
                    "out_tok": msg.usage.output_tokens,
                    "code_len": len(code), "code": code,
                })
                OUT.write_text(json.dumps(results, indent=1))
                ok = sum(1 for v in compliance.values() if v is True)
                na = sum(1 for v in compliance.values() if v is None)
                print(f"  size={size:3d} {task_id:14s} rep{rep}  pass={ok}/{10-na} (n/a {na})",
                      file=sys.stderr)
                time.sleep(1)
    print(f"  DONE {len(results)} runs", file=sys.stderr)

if __name__ == "__main__":
    main()
