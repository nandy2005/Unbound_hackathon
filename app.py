import os
import asyncio
import httpx
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

UNBOUND_API_KEY = os.getenv("UNBOUND_API_KEY")

app = FastAPI()

templates = Jinja2Templates(directory=".")

# ----------------------------
# In-Memory Storage
# ----------------------------
WORKFLOWS = {}
RUNS = {}


# ----------------------------
# Unbound API Call
# ----------------------------
async def call_unbound(model, prompt):

    url = "https://api.getunbound.ai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {UNBOUND_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    async with httpx.AsyncClient(timeout=60, verify=False) as client:
        r = await client.post(url, json=payload, headers=headers)

    r.raise_for_status()

    data = r.json()

    return data["choices"][0]["message"]["content"]


def check(output, rule):

    if rule.startswith("contains:"):
        return rule.replace("contains:", "") in output

    if rule == "not_empty":
        return len(output.strip()) > 10

    return False


# ----------------------------
# Runner
# ----------------------------
async def run_workflow(wf_id):

    wf = WORKFLOWS[wf_id]

    context = ""

    RUNS[wf_id] = []

    for i, step in enumerate(wf["steps"]):

        RUNS[wf_id].append(f"▶ Step {i+1} started")

        success = False

        for attempt in range(3):

            prompt = f"""
Context:
{context}

Task:
{step['prompt']}
"""

            RUNS[wf_id].append(f"Attempt {attempt+1}")

            try:
                out = await call_unbound(
                    step["model"],
                    prompt
                )

            except Exception as e:
                RUNS[wf_id].append(f"API Error: {e}")
                continue

            RUNS[wf_id].append("Output:")
            RUNS[wf_id].append(out[:500] + "...")

            if check(out, step["criteria"]):

                RUNS[wf_id].append("✅ Passed")

                context = out
                success = True
                break

            else:
                RUNS[wf_id].append("Failed")

        if not success:
            RUNS[wf_id].append(" Workflow Failed")
            return

    RUNS[wf_id].append(" Workflow Complete")


# ----------------------------
# UI
# ----------------------------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):

    return """
    <html>
    <body style="font-family:Arial;padding:30px">

    <h1>Agentic Workflow Builder</h1>

    <form method="post" action="/create">

    <h3>Step 1</h3>
    Model: <input name="m1" value="gpt-4"><br>
    Prompt:<br>
    <textarea name="p1" rows="3" cols="60"></textarea><br>
    Criteria: <input name="c1" value="not_empty"><br>

    <h3>Step 2</h3>
    Model: <input name="m2" value="gpt-4"><br>
    Prompt:<br>
    <textarea name="p2" rows="3" cols="60"></textarea><br>
    Criteria: <input name="c2" value="not_empty"><br>

    <br>
    <button>Create & Run</button>

    </form>

    </body>
    </html>
    """


# ----------------------------
# Create + Run
# ----------------------------
@app.post("/create")
async def create(
    m1=Form(...), p1=Form(...), c1=Form(...),
    m2=Form(...), p2=Form(...), c2=Form(...)
):

    wf_id = len(WORKFLOWS) + 1

    WORKFLOWS[wf_id] = {
        "steps": [
            {
                "model": m1,
                "prompt": p1,
                "criteria": c1
            },
            {
                "model": m2,
                "prompt": p2,
                "criteria": c2
            }
        ]
    }

    asyncio.create_task(run_workflow(wf_id))

    return RedirectResponse(f"/run/{wf_id}", 302)


# ----------------------------
# Logs
# ----------------------------
@app.get("/run/{wf_id}", response_class=HTMLResponse)
async def logs(wf_id: int):

    logs = RUNS.get(wf_id, [])

    html = "<h2>Workflow Run</h2><pre>"

    for l in logs:
        html += l + "\n\n"

    html += "</pre>"

    html += """
    <script>
      setTimeout(()=>location.reload(),2000);
    </script>
    """

    return html
