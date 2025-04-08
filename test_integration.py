from web_search import GoogleSearch

def main():
    searcher = GoogleSearch()
    results = searcher.search("Python 3.12 release date")
    
    if results:
        print("First result:")
        print(f"Title: {results[0]['title']}")
        print(f"URL: {results[0]['link']}")
    else:
        print("No results found")

if __name__ == "__main__":
    main()