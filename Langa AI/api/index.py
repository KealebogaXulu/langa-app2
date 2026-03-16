import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import io, time, json, re, os, requests
from google import genai

app = FastAPI()

# Enable CORS for Netlify handshake
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

SNIPER_PROMPT = """
ACT AS: A Technical Lead & Forensic Recruiter.
MISSION: Analyze the provided Job Data and extract a Tactical Infiltration Brief.

OUTPUT ONLY VALID JSON WITH THESE FIELDS:
1. "ghost_score": (1-10) How likely is this a 'Ghost Job'?
2. "burning_house": What is the #1 operational catastrophe this hire solves?
3. "tech_debt": Identify legacy issues or 'faked' processes.
4. "asymmetric_hook": A 2-sentence opener for a DM: "I noticed [detail]..." 
5. "interrogation": 2 questions to flip the power dynamic.
6. "privacy_status": "DATA_PURGED"
"""

def run_langa_core(job_url):
    try:
        time.sleep(1.5)
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(job_url, headers=headers, timeout=12)
        clean_content = re.sub(r'<(script|style).*?>.*?</\1>', '', r.text, flags=re.DOTALL)
        clean_content = re.sub(r'<.*?>', ' ', clean_content)
        
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=f"{SNIPER_PROMPT}\n\nDATA:\n{clean_content[:25000]}"
        )
        json_str = re.sub(r'```json|```', '', response.text).strip()
        return json.loads(json_str)
    except Exception as e:
        return {"error": str(e)}

@app.post("/scan-single")
async def scan_single(url: str = Form(...)):
    return JSONResponse(content=run_langa_core(url))

@app.post("/process-csv")
async def process_csv(file: UploadFile = File(...)):
    contents = await file.read()
    df = pd.read_csv(io.BytesIO(contents))
    potential_cols = ['url', 'job_url', 'link']
    target_col = next((c for c in df.columns if c.lower() in potential_cols), df.columns[0])
    
    results = [run_langa_core(str(url)) for url in df[target_col]]
    final_df = pd.concat([df, pd.json_normalize(results)], axis=1)
    
    path = "/tmp/Langa_Brief.csv" if os.name != 'nt' else "Langa_Brief.csv"
    final_df.to_csv(path, index=False)
    return FileResponse(path, filename="Langa_Tactical_Brief.csv")