import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import io, json, re, os, requests
from google import genai

app = FastAPI()

# SECURITY: Allow your Netlify/Vercel front-end to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def run_langa_core(job_url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
        r = requests.get(job_url, headers=headers, timeout=10)
        # Strip HTML noise
        text = re.sub(r'<script.*?</script>|<style.*?</style>|<.*?>', ' ', r.text, flags=re.DOTALL)
        
        prompt = "Analyze this job post. Output JSON only: {ghost_score: 1-10, burning_house: str, tech_debt: str, asymmetric_hook: str, interrogation: str}"
        
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=f"{prompt}\n\nDATA:\n{text[:15000]}"
        )
        # Clean AI markdown formatting
        json_str = re.sub(r'```json|```', '', response.text).strip()
        return json.loads(json_str)
    except Exception as e:
        return {"error": "Target unreachable or link blocked."}

@app.post("/api/scan-single")
async def scan_single(url: str = Form(...)):
    return JSONResponse(content=run_langa_core(url))

@app.post("/api/process-csv")
async def process_csv(file: UploadFile = File(...)):
    df = pd.read_csv(io.BytesIO(await file.read()))
    target_col = next((c for c in df.columns if 'url' in c.lower() or 'link' in c.lower()), df.columns[0])
    
    results = [run_langa_core(url) for url in df[target_col]]
    final_df = pd.concat([df, pd.json_normalize(results)], axis=1)
    
    # Vercel uses /tmp for temporary file storage
    output_path = "/tmp/Langa_Batch.csv"
    final_df.to_csv(output_path, index=False)
    return FileResponse(output_path, filename="Langa_Batch.csv")
