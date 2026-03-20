# Use this to obtain filing for briefs from edgar API 

import requests
import time
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Jack Zhou jackzhou018@gmail.com"  # required by SEC
}




# turn url to text in SEC/EDGAR domain sites
def sec_get(url, headers=headers):
    reponse = requests.get(url, headers=headers)
    time.sleep(0.1) # request limit for SEC
    return reponse

# get's filings and returns an array of dicts for specified company and form type  
def get_filings(cik, form_type = "10-K"):

    cik = str(cik).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    response = sec_get(url)
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


# returns 10-k file for given company 
def get_filings_text(cik, accession):
    accession_no_dashes = accession.replace("-", "")
    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{accession}-index.htm"
    index = sec_get(index_url)
    soup = BeautifulSoup(index.text, "html.parser")
    for row in soup.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) > 3:
            if cols[3].get_text(strip=True) == "10-K":
                link = "https://www.sec.gov" + cols[2].find("a")["href"]
                link = link.replace("/ix?doc=", "")
                response = sec_get(link)
                return response.text
            
            
    return 



    
















print(get_filings(320193))
print(get_filings_text(320193, "0000320193-19-000119"))
