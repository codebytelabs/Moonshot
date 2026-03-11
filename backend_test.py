#!/usr/bin/env python3

import requests
import json
import time
import sys
from datetime import datetime

class ApexSwarmTester:
    def __init__(self):
        self.base_url = "https://swarm-command-center.preview.emergentagent.com"
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def run_test(self, name: str, method: str, endpoint: str, expected_status: int = 200, data: dict = None, timeout: int = 30):
        """Run a single API test"""
        url = f"{self.base_url}{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ PASSED - Status: {response.status_code}")
                try:
                    result = response.json()
                    print(f"   Response keys: {list(result.keys()) if isinstance(result, dict) else 'Array/Other'}")
                    return True, result
                except:
                    return True, response.text
            else:
                print(f"❌ FAILED - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                self.failed_tests.append(f"{name}: {response.status_code}")
                return False, {}

        except Exception as e:
            print(f"❌ FAILED - Error: {str(e)}")
            self.failed_tests.append(f"{name}: {str(e)}")
            return False, {}

    def test_health(self):
        """Test health endpoint"""
        return self.run_test("Health Check", "GET", "/api/health")

    def test_dashboard(self):
        """Test dashboard endpoint"""
        return self.run_test("Dashboard Data", "GET", "/api/dashboard")

    def test_agent_logs(self):
        """Test agent logs endpoint"""
        return self.run_test("Agent Logs", "GET", "/api/agent-logs")

    def test_alpha_hits(self):
        """Test alpha hits endpoint"""
        return self.run_test("Alpha Hits", "GET", "/api/alpha-hits")

    def test_trades(self):
        """Test trades endpoint"""
        return self.run_test("Trades History", "GET", "/api/trades")

    def test_positions(self):
        """Test positions endpoint"""
        success, result = self.run_test("Positions", "GET", "/api/positions")
        if success and isinstance(result, list):
            print(f"   Found {len(result)} positions")
            if len(result) >= 3:
                symbols = [p.get('symbol', 'N/A') for p in result[:3]]
                print(f"   Seed positions: {symbols}")
        return success, result

    def test_portfolio(self):
        """Test portfolio endpoint"""
        return self.run_test("Portfolio History", "GET", "/api/portfolio")

    def test_settings(self):
        """Test settings endpoint"""
        success, result = self.run_test("Settings", "GET", "/api/settings")
        if success:
            print(f"   Primary model: {result.get('primary_model', 'N/A')}")
            print(f"   Chains: {len(result.get('chains', []))}")
        return success, result

    def test_swarm_start(self):
        """Test swarm start endpoint"""
        success, result = self.run_test("Swarm Start", "POST", "/api/swarm/start")
        if success:
            print(f"   Status: {result.get('status', 'N/A')}")
        return success, result

    def test_swarm_stop(self):
        """Test swarm stop endpoint"""
        success, result = self.run_test("Swarm Stop", "POST", "/api/swarm/stop")
        if success:
            print(f"   Status: {result.get('status', 'N/A')}")
        return success, result

    def test_dex_trending(self):
        """Test DexScreener trending endpoint"""
        return self.run_test("DexScreener Trending", "GET", "/api/dex/trending", timeout=15)

    def test_dex_search(self):
        """Test DexScreener search endpoint"""
        return self.run_test("DexScreener Search", "GET", "/api/dex/search?q=PEPE", timeout=15)

    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 APEX-SWARM API Testing Started")
        print("=" * 50)
        
        start_time = time.time()
        
        # Core API tests
        self.test_health()
        self.test_dashboard()
        self.test_agent_logs()
        self.test_alpha_hits()
        self.test_trades()
        self.test_positions()
        self.test_portfolio()
        self.test_settings()
        
        # Swarm control tests
        self.test_swarm_start()
        time.sleep(2)  # Wait for swarm to start
        self.test_swarm_stop()
        
        # External API tests
        self.test_dex_trending()
        self.test_dex_search()
        
        # Summary
        duration = time.time() - start_time
        print("\n" + "=" * 50)
        print(f"📊 Test Results Summary")
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%")
        print(f"Duration: {duration:.2f}s")
        
        if self.failed_tests:
            print(f"\n❌ Failed Tests:")
            for failure in self.failed_tests:
                print(f"   - {failure}")
        else:
            print(f"\n✅ All tests passed!")
            
        return self.tests_passed == self.tests_run

def main():
    tester = ApexSwarmTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())