# Use this to obtain filing for briefs from edgar API 

import requests
import time

headers = {
    "User-Agent": "Your Name yourname@email.com"  # required by SEC
}

# Get all filings for a company by CIK number
# Apple = 0000320193
def get_filings(cik, form_type="10-K"):
    cik = str(cik).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    r = requests.get(url, headers=headers)
    data = r.json()
    
    filings = data["filings"]["recent"]
    results = []
    for i, form in enumerate(filings["form"]):
        if form == form_type:
            results.append({
                "date": filings["filingDate"][i],
                "accession": filings["accessionNumber"][i],
                "form": form
            })
    return results