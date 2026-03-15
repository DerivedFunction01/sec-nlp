import sys
import requests
import webpage
webpage.DEBUG = True

def test_url(url: str):
    print(f"\n🌐 Fetching {url}...")
    headers = {"User-Agent": "test-script@example.com"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"❌ Failed to fetch: HTTP {resp.status_code}")
        return
    
    raw_text = resp.text
    
    is_20f, is_40f, home_country, _ = webpage.detect_filing_type(url, raw_text)
    form_type = "20-F" if is_20f else "40-F" if is_40f else "10-K"
    print(f"📄 Detected form type: {form_type} (Home Country: {home_country})")
    
    print("⏳ Parsing multi-document content (this might take a few seconds)...")
    docs = webpage.parse_multi_document_content(raw_text)
    if not docs:
        print("❌ No documents found.")
        return
        
    main_doc = docs[0]
    print(f"✅ Extracted main document (length: {len(main_doc)} chars)")
    
    blocks = webpage.filter_paragraphs_loose(main_doc)
    print(f"🧱 Total initial blocks: {len(blocks)}")
    
    print("\n" + "="*50 + "\n1. PREFILTER STAGE\n" + "="*50)
    prefiltered_blocks = webpage.prefilter_blocks(blocks)
    prefilter_dropped = [b for b in blocks if b not in prefiltered_blocks]
    print(f"Dropped {len(prefilter_dropped)} structural/noise blocks.")
            
    print("\n" + "="*50 + "\n2. COVER PAGE STAGE\n" + "="*50)
    post_cover_blocks, cover_dropped_count = webpage.drop_cover_page(prefiltered_blocks)
    cover_dropped = prefiltered_blocks[:cover_dropped_count]
    print(f"Dropped {cover_dropped_count} blocks as cover page.")
    if cover_dropped:
        print("Last 3 blocks dropped in cover page:")
        for b in cover_dropped[-3:]:
            print(f"  🗑️  {repr(b[:120])}...")
            
    print("\n" + "="*50 + "\n3. TABLE OF CONTENTS STAGE\n" + "="*50)
    final_blocks, toc_dropped_count = webpage.drop_table_of_contents(post_cover_blocks, form_type=form_type)
    toc_dropped = post_cover_blocks[:toc_dropped_count]
    print(f"Dropped {toc_dropped_count} blocks as TOC.")
    if toc_dropped:
        print("Last 5 blocks dropped in TOC:")
        for b in toc_dropped[-5:]:
            print(f"  🗑️  {repr(b[:120])}...")
    
    print("\n" + "="*50 + "\n✅ FINAL OUTPUT\n" + "="*50)
    print(f"Remaining active blocks: {len(final_blocks)}")
    if final_blocks:
        print("First 5 KEPT blocks:")
        for b in final_blocks[:5]:
            print(f"  🟢 {repr(b[:120])}...")

if __name__ == '__main__':
    input_url = sys.argv[1] if len(sys.argv) > 1 else input("Enter SEC filing URL: ").strip()
    if input_url:
        test_url(input_url)
