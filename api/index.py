from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

import os
import re
import io
import json
import requests
import pandas as pd

from google import genai

app = FastAPI()

# Allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def run_langa_core(job_url):

    try:

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
        }

        r = requests.get(job_url, headers=headers, timeout=10)

        # Remove HTML noise
        text = re.sub(
            r"<script.*?</script>|<style.*?</style>|<.*?>",
            " ",
            r.text,
            flags=re.DOTALL,
        )

        text = re.sub(r"\s+", " ", text)

        prompt = """
Analyze the following job post.

Return ONLY valid JSON.

Structure:
{
 "ghost_score": 1-10,
 "burning_house": "what problem the company is desperate to solve",
 "tech_debt": "technical mess hinted in the description",
 "asymmetric_hook": "a unique angle a candidate could use to stand out",
 "interrogation": "one powerful question to ask the recruiter"
}
"""

        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=f"{prompt}\n\nJOB DATA:\n{text[:15000]}",
        )

        # Clean markdown formatting
        cleaned = re.sub(r"```json|```", "", response.text).strip()

        return json.loads(cleaned)

    except Exception:
        return {"error": "Target unreachable or link blocked."}


@app.post("/api/scan-single")
async def scan_single(url: str = Form(...)):

    result = run_langa_core(url)

    return JSONResponse(content=result)


@app.post("/api/process-csv")
async def process_csv(file: UploadFile = File(...)):

    df = pd.read_csv(io.BytesIO(await file.read()))

    target_col = next(
        (c for c in df.columns if "url" in c.lower() or "link" in c.lower()),
        df.columns[0],
    )

    results = [run_langa_core(url) for url in df[target_col]]

    final_df = pd.concat([df, pd.json_normalize(results)], axis=1)

    # Vercel only allows temporary files in /tmp
    output_path = "/tmp/Langa_Batch.csv"

    final_df.to_csv(output_path, index=False)

    return FileResponse(output_path, filename="Langa_Batch.csv")
@app.get("/api/health")
def health():
    return {"status": "LANGA online"}
