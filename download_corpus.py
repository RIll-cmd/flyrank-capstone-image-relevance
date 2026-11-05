"""Download a small, attributed Wikimedia Commons corpus using its public API."""
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import unquote, urlparse
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).parent
OUT=ROOT/'images'
API='https://commons.wikimedia.org/w/api.php'
HEADERS={'User-Agent':'FlyRankImageMatchingCapstone/1.0 (educational image research)'}
TERMS=['red fox','gray wolf','domestic dog','brown bear']

def clean(value): return BeautifulSoup(value or '', 'html.parser').get_text(' ',strip=True)

def main():
    OUT.mkdir(exist_ok=True)
    saved=ROOT/'corpus.json'
    if saved.exists():
        manifest=json.loads(saved.read_text(encoding='utf8'))
        for item in manifest:
            dest=OUT/item['path']
            if dest.exists(): continue
            title=unquote(urlparse(item['source']).path.rsplit('/',1)[-1]).replace('_',' ')
            response=requests.get(API,headers=HEADERS,timeout=30,params={'action':'query','titles':title,'prop':'imageinfo','iiprop':'url','iiurlwidth':640,'format':'json'})
            response.raise_for_status()
            pages=response.json()['query']['pages']
            url=next(iter(pages.values()))['imageinfo'][0]['thumburl']
            time.sleep(0.3); image=requests.get(url,headers=HEADERS,timeout=30); image.raise_for_status(); dest.write_bytes(image.content)
        print('Restored',len(manifest),'manifest entries. Review each source license before use.')
        return
    manifest=[]
    for term in TERMS:
        response=requests.get(API,headers=HEADERS,timeout=30,params={'action':'query','generator':'search','gsrsearch':term+' filetype:bitmap','gsrnamespace':6,'gsrlimit':40,'prop':'imageinfo','iiprop':'url|extmetadata','iiurlwidth':640,'format':'json'})
        response.raise_for_status()
        pages=sorted(response.json().get('query',{}).get('pages',{}).values(),key=lambda x:x.get('index',999))
        count=0
        for page in pages:
            info=(page.get('imageinfo') or [{}])[0]; meta=info.get('extmetadata',{})
            license_name=clean(meta.get('LicenseShortName',{}).get('value',''))
            if not re.search(r'^(CC BY(?:-SA)? [234]\.0|CC0|Public domain)',license_name,re.I): continue
            url=info.get('thumburl'); original=info.get('descriptionurl')
            if not url or not original or not re.search(r'\.(jpg|jpeg|png)(?:\?|$)',url,re.I): continue
            name=hashlib.sha256(original.encode()).hexdigest()[:16]+'.jpg'
            dest=OUT/name
            if not dest.exists():
                time.sleep(0.3); image=requests.get(url,headers=HEADERS,timeout=30); image.raise_for_status(); dest.write_bytes(image.content)
            manifest.append({'path':name,'source':original,'license':license_name,'license_url':meta.get('LicenseUrl',{}).get('value',''),'creator':clean(meta.get('Artist',{}).get('value','')),'search_term':term})
            count+=1
            if count>=10: break
        print(term,count,flush=True)
    (ROOT/'corpus.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf8')
    print('Downloaded',len(manifest),'images. Check each license and content before submission.')

if __name__=='__main__': main()
