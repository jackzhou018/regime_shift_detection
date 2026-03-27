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
import sqlite3
import requests






headers = {
    "User-Agent": "Jack Zhou jackzhou018@gmail.com"  # required by SEC
}

sp500_ciks = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "AMZN": "0001018724",
    "GOOGL": "0001652044",
    "GOOG": "0001652044",
    "META": "0001326801",
    "NVDA": "0001045810",
    "TSLA": "0001318605",
    "BRK.B": "0001067983",
    "JPM": "0000019617",
    "V": "0001403161",
    "JNJ": "0000200406",
    "UNH": "0000731766",
    "PG": "0000080424",
    "XOM": "0000034088",
    "HD": "0000354950",
    "MA": "0001141391",
    "CVX": "0000093410",
    "PFE": "0000078003",
    "KO": "0000021344",
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
    embedding = model.encode(text)
    return embedding

# get embeddings of a file 
def get_embeddings(filings, aggregate_embeddings): 
    embeddings = {}
    for i, file in enumerate(filings):
        # check if file is already in database
        if already_processed(cursor, file["accession"]):
            # retrieve embedding from database
            embedding = retrieve_embedding(cursor, file["accession"])
            if embedding is not None:
                embeddings[file["date"]] = embedding
                embeddings["quarter"] = pd.Timestamp(file["date"]).to_period("Q")
                aggregate_embeddings[embeddings["quarter"]].append(embedding)
            continue
        html_text = get_filings_text(cik, file["accession"])        
        mdna = extract_mdna(html_text)
        if mdna != None:
            embedding = embed(mdna)
            embeddings[file["date"]] = embedding
            # using date -> put it into a bucket (quarter) of form ####Q# eg. 2019Q1
            embeddings["quarter"] = pd.Timestamp(file["date"]).to_period("Q")
            aggregate_embeddings[embeddings["quarter"]].append(embedding)
            # cache filings to permanent database to avoid reprocessing
            cache_filings(cursor, cik, file, embedding.tobytes())
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
    

def already_processed(cursor, accession):
    cursor.execute("SELECT 1 FROM filings WHERE accession = ?", (accession,))
    return cursor.fetchone() is not None

def cache_filings(cursor, cik, file, embedding):
        # store in database instead of just a dict
        cursor.execute("INSERT INTO filings (cik, date, accession, form_type, embedding) VALUES (?, ?, ?, ?, ?)", 
                    (cik, file["date"], file["accession"], file["form_type"], embedding))
        conn.commit()

def retrieve_embedding(cursor, accession):
    '''
    retrieves embedding from database for given accession number, returns as numpy array
    '''
    cursor.execute("SELECT embedding FROM filings WHERE accession = ?", (accession,))
    result = cursor.fetchone()
    if result:
        return np.frombuffer(result[0], dtype=np.float32)
    else:
        return None






if __name__ == "__main__":
    #  0000320193-19-000119
    #print(get_filings(320193))
    #html_text = get_filings_text(320193, "0000320193-25-000079")

    # database setup
    conn = sqlite3.connect("edgar.db")
    cursor = conn.cursor()
    # make sure to convert embedding to bytes before storing in database, and convert back to numpy array after retrieving from database
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS filings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cik TEXT,
            date TEXT,
            accession TEXT,
            form_type TEXT,
            mdna TEXT
            embedding BLOB 
        )
    """)
    conn.commit()

    
    model = SentenceTransformer("all-MiniLM-L6-v2")
    aggregate_embeddings = defaultdict(list)

    # loop through each company, get filings, extract mdna, embed, and store in aggregate embeddings by quarter
    for cik in sp500_ciks.values():
        
        filings = get_filings(cik)
        # i want to store some metadata for each company so function returns company embedding, but changes aggregate embedding within function
        total, embeddings = get_embeddings(filings, aggregate_embeddings)
    
    # average embeddings in each quarter to get market embedding, then compute similarity between quarters 
    market_embeddings = average_quarters(aggregate_embeddings)
    sims = cos_sim(market_embeddings)
    print(sims)

    cursor.close()
    conn.close()





