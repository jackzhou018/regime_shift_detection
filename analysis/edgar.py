# Use this to obtain filing for briefs from edgar API 

import requests
import time
from bs4 import BeautifulSoup
import re
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
from collections import defaultdict




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


# extract item 7 of the filing for manager opinion
def extract_mdna(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    
    item7_tags = []
    item8_tags = []
    for tag in soup.find_all(["b", "strong", "span", "p", "div"]):
        style = tag.get("style", "")
        text = tag.get_text(strip=True)
        
        # check if bold - either via tag name or css style
        is_bold = (
            tag.name in ["b", "strong"] or
            "font-weight:700" in style or
            "font-weight: 700" in style or
            "font-weight:bold" in style or
            "font-weight: bold" in style
        ) 
        if is_bold:
            if re.search(r"Item\s*7[^A-Za-z]", text, re.IGNORECASE):
                item7_tags.append(tag)
            if re.search(r"Item\s*8[^A-Za-z]", text, re.IGNORECASE):
                item8_tags.append(tag)

    if len(item7_tags) == 0: 
        print("Item 7 tag coudn't be found")
        return None
    else:
        item7_tag = item7_tags[-1]
    if len(item8_tags) == 0: 
        print("Item 8 tag coudn't be found")
        return None
    else:
        item8_tag = item8_tags[-1]

    full_text = soup.get_text(separator=" ")
    item7_text = item7_tag.get_text(strip=True)
    item8_text = item8_tag.get_text(strip=True)

    item7_pos = full_text.rfind(item7_text)
    item8_pos = full_text.rfind(item8_text)

    mdna = full_text[item7_pos:item8_pos]
    return mdna

# turn text to an embedded vector 
def embed(text):
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embedding = model.encode(text)
    return embedding

# get embeddings of a file 
def get_embeddings(filings, aggregate_embeddings): 
    embeddings = {}
    for i, file in enumerate(filings):
        html_text = get_filings_text(cik, file["accession"])        
        mdna = extract_mdna(html_text)
        if mdna != None:
            embedding = embed(mdna)
            embeddings[file["date"]] = embedding
            # using date -> put it into a bucket (quarter) of form ####Q# eg. 2019Q1
            embeddings["quarter"] = pd.Timestamp(file["date"]).to_period("Q")
            aggregate_embeddings[embeddings["quarter"]].append(embedding)
    total = len(embeddings)
    return total, embeddings

# average all embeddings in each quarter
def average_quarters(aggregate_embeddings):
    '''
    market_embeddings structure is: quarter: 384D vector representing the mean embedding 
    '''
    market_embeddings = {}
    for quarter, embeddings in aggregate_embeddings.items():
        market_embeddings[quarter] = np.mean(embeddings, axis=0)
    return market_embeddings


# use cosin_similarity to see how closely related embeddings are between years 
def cos_sim(market_embeddings):
    '''
    returns dictionary of form quarter->other quarter: similarity float
    '''
    sims = {}
    quarters = sorted(market_embeddings.keys(), key=lambda x: pd.Period(x, "Q"))    
    for i in range(len(quarters) - 1):
        sim = cosine_similarity([market_embeddings[quarters[i]]], [market_embeddings[quarters[i+1]]])[0][0]
        sims[f"{quarters[i]}->{quarters[i+1]}"] = sim
    return sims
    








if __name__ == "__main__":
    #  0000320193-19-000119
    #print(get_filings(320193))
    #html_text = get_filings_text(320193, "0000320193-25-000079")

    cik = 320193
    filings = get_filings(cik)

    aggregate_embeddings = defaultdict(list)

    # i want to store some metadata for each company so function returns company embedding, but changes aggregate embedding within function
    total, embeddings = get_embeddings(filings, aggregate_embeddings)

    market_embeddings = average_quarters(aggregate_embeddings)
    sims = cos_sim(market_embeddings)




