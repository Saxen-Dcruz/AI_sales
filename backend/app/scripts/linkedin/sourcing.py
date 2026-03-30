from ddgs import DDGS
import time

def find_companies_at_scale():
    # 1. The Niche List
    sub_niches = [
        "automotive manufacturing", "textile manufacturing", "chemical manufacturing",
        "electronics manufacturing", "pharmaceutical manufacturing", "aerospace manufacturing",
        "food processing", "CNC machining", "plastic injection molding", "sheet metal fabrication"
    ]
    
    # 2. 🚀 THE CITY MATRIX 🚀 
    # Add major industrial hubs here to force DDG to give us local, untapped companies
    cities = [
        "Pune", "Chennai", "Coimbatore", "Ahmedabad", "Surat", 
        "Ludhiana", "Faridabad", "Baddi", "Pimpri-Chinchwad", "Peenya","bengaluru"
    ]
    
    all_urls = set() 
    
    print("🚀 Starting Matrix Search (Niches x Cities)...")
    
    with DDGS() as ddgs:
        # Loop through every city, and inside that, every niche
        for city in cities:
            print(f"\n🏙️ --- Targeting City: {city} ---")
            for niche in sub_niches:
                # We swapped "India" for the specific city!
                query = f'site:linkedin.com/company/ "{niche}" "{city}" India'
                
                try:
                    results = ddgs.text(query, max_results=20)
                    added_count = 0
                    if results:
                        for r in results:
                            clean_url = r.get('href', '').split('?')[0]
                            if "linkedin.com/company/" in clean_url and "/dir/" not in clean_url:
                                # Clean the URL right at the source so it perfectly matches the DB
                                if clean_url.endswith('/'):
                                    clean_url = clean_url[:-1]
                                if not clean_url.endswith('/about'):
                                    clean_url = f"{clean_url}/about"
                                    
                                all_urls.add(clean_url)
                                added_count += 1
                            
                    print(f"  🦆 {niche}: Found {added_count} URLs")
                except Exception as e:
                    print(f"  ⚠️ Error on {niche} in {city}: {e}")
                    
                time.sleep(3) # Keep the sleep so DDG doesn't ban us
            
    print(f"\n🎉 Search Complete! Gathered {len(all_urls)} unique company URLs.")
    return list(all_urls)

def find_decision_makers(company_name, job_title="Plant Manager", num_results=50):
    print(f"🔍 Searching for {job_title}s at {company_name}...")
    query = f'site:linkedin.com/in/ "{company_name}" "{job_title}"'
    urls = []
    
    try:
        results = DDGS().text(query, max_results=num_results)
        
        for r in results:
            link = r.get('href', '')
            clean_url = link.split('?')[0]
            if "linkedin.com/in/" in clean_url and "/dir/" not in clean_url:
                if clean_url not in urls:
                    urls.append(clean_url)
    except Exception as e:
        print(f"❌ DuckDuckGo Error: {e}")
        
    return urls