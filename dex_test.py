#!/usr/bin/env python3

import requests
import json
import sys

class DexScreenerTester:
    def __init__(self):
        self.base_url = "https://cc2a309c-c8b5-4c0d-b1c5-1710285173cf.preview.emergentagent.com"
        
    def api_call(self, method: str, endpoint: str, data: dict = None):
        """Make API call and return response"""
        url = f"{self.base_url}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ API Error ({endpoint}): {str(e)}")
            return None

    def test_dex_endpoints(self):
        """Test DexScreener API endpoints"""
        print("🔗 DexScreener API Test Started")
        print("=" * 50)
        
        # Test trending endpoint
        print("\n📈 Testing GET /api/dex/trending...")
        trending = self.api_call("GET", "/api/dex/trending")
        if trending:
            boosted = trending.get('boosted', [])
            top = trending.get('top', [])
            print(f"✅ PASS: Retrieved {len(boosted)} boosted + {len(top)} top tokens")
            
            if boosted and len(boosted) > 0:
                print(f"   Sample boosted: {boosted[0].get('tokenAddress', 'N/A')[:16]}...")
            if top and len(top) > 0:
                print(f"   Sample top: {top[0].get('tokenAddress', 'N/A')[:16]}...")
        else:
            print("❌ FAIL: Could not retrieve trending data")
            return False
        
        # Test search endpoint with PEPE
        print(f"\n🔍 Testing GET /api/dex/search?q=PEPE...")
        search = self.api_call("GET", "/api/dex/search?q=PEPE")
        if search:
            pairs = search.get('pairs', [])
            print(f"✅ PASS: Found {len(pairs)} PEPE pairs")
            
            if pairs and len(pairs) > 0:
                sample = pairs[0]
                base_symbol = sample.get('baseToken', {}).get('symbol', 'N/A')
                quote_symbol = sample.get('quoteToken', {}).get('symbol', 'N/A')
                chain = sample.get('chainId', 'N/A')
                print(f"   Sample pair: {base_symbol}/{quote_symbol} on {chain}")
        else:
            print("❌ FAIL: Could not search for PEPE pairs")
            return False
            
        print(f"\n✅ All DexScreener endpoints working correctly!")
        return True

def main():
    tester = DexScreenerTester()
    success = tester.test_dex_endpoints()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())