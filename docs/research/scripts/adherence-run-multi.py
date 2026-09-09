"""Same rules, same tasks, different vendors: Problem 4."""
import json, os, pathlib, random, sys, threading
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "/tmp/adherence")
from rules import CHECKS, FILLER
from run import build_rules, extract_code, TASKS, SIZES, REPS

OUT = pathlib.Path(os.environ.get("ADH_OUT", "/tmp/adherence/multi_v2.json"))
LOCK = threading.Lock()
ALL_MODELS = [("openai", "gpt-5"), ("google", "gemini-2.5-pro")]
MODELS = [m for m in ALL_MODELS if len(sys.argv) < 2 or m[0] == sys.argv[1]]

def call(provider, model, system, task):
    if provider == "openai":
        from openai import OpenAI
        c = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        r = c.chat.completions.create(model=model, messages=[
            {"role": "system", "content": system}, {"role": "user", "content": task}])
        return r.choices[0].message.content, r.usage.prompt_tokens, r.usage.completion_tokens
    from google import genai
    from google.genai import types
    c = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    r = c.models.generate_content(model=model, contents=task,
        config=types.GenerateContentConfig(system_instruction=system))
    u = r.usage_metadata
    return r.text, u.prompt_token_count, u.candidates_token_count

def one(provider, model, size, tid, task, rep):
    rng = random.Random(f"{size}-{tid}-{rep}")
    body, positions = build_rules(size, rng)
    system = ("You are contributing to an existing Python codebase. "
              "Follow every one of these project rules exactly:\n\n" + body)
    try:
        text, itok, otok = call(provider, model, system, task)
    except Exception as e:
        print(f"  ERR {model} {size}/{tid}/{rep}: {str(e)[:70]}", file=sys.stderr)
        return None
    code = extract_code(text or "")
    comp = {}
    for k, v in CHECKS.items():
        try: comp[k] = v["fn"](code)
        except Exception: comp[k] = None
    ok = sum(1 for v in comp.values() if v is True); na = sum(1 for v in comp.values() if v is None)
    print(f"  {model:16s} size={size:3d} {tid:13s} r{rep} pass={ok}/{10-na}", file=sys.stderr)
    return {"model": model, "provider": provider, "size": size, "task": tid, "rep": rep,
            "compliance": comp, "positions": positions, "in_tok": itok, "out_tok": otok, "code": code}

def main():
    cur = json.loads(OUT.read_text()) if OUT.exists() else []
    done = {(x["model"], x["size"], x["task"], x["rep"]) for x in cur}
    todo = [(p, m, s, tid, t, rep) for p, m in MODELS for s in SIZES
            for tid, t in TASKS for rep in range(REPS)
            if (m, s, tid, rep) not in done]
    print(f"  todo: {len(todo)}", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=8) as ex:
        for f in [ex.submit(one, *a) for a in todo]:
            r = f.result()
            if r:
                with LOCK:
                    c = json.loads(OUT.read_text()) if OUT.exists() else []
                    if (r["model"], r["size"], r["task"], r["rep"]) not in {
                        (x["model"], x["size"], x["task"], x["rep"]) for x in c}:
                        c.append(r)
                    OUT.write_text(json.dumps(c, indent=1))
    print("  DONE", file=sys.stderr)

main()
