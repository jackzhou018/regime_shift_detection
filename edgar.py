# Use this to obtain filing for briefs from edgar API 

import requests
import time

headers = {
    "User-Agent": "Jack Zhou jackzhou018@gmail.com"  # required by SEC
}



def getfilings(cik, form_type = "10-K"):

    cik = str(cik).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    response = requests.get(url, headers=headers)
    data = response.json()
    filings = data["filings"]["recent"]
    arr = []

    for i, value in enumerate(filings["form"]):
        if value == form_type:
            arr.append({
                "date": filings["filingDate"][i],
                "accession": filings["accessionNumber"][i],
                "form": value
            }
            )
    return arr 
            

















print(getfilings(320193))
