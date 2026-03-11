"""
Gate.io Testnet Connector.
Enables real API order execution on Gate.io demo environment.
"""
import time
import hmac
import hashlib
import asyncio
from typing import Dict, Optional, List
from loguru import logger
import httpx


class GateIOTestnetConnector:
    """
    Gate.io testnet connector with real API order execution.
    
    Uses HMAC-SHA512 authentication and exponential backoff retry logic.
    """
    
    def __init__(self, api_key: str, secret_key: str, testnet_url: str):
        """
        Initialize Gate.io testnet connector.
        
        Args:
            api_key: Gate.io testnet API key
            secret_key: Gate.io testnet secret key
            testnet_url: Base URL for testnet API (https://api-testnet.gateapi.io/api/v4)
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = testnet_url.rstrip('/')
        self.max_retries = 3
        self.base_retry_delay = 2.0  # seconds
        
        logger.info(f"Gate.io testnet connector initialized: {self.base_url}")
    
    def _generate_signature(self, method: str, url_path: str, query_string: str = "", body: str = "") -> Dict[str, str]:
        """
        Generate HMAC-SHA512 signature for Gate.io API authentication.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url_path: API endpoint path
            query_string: Query parameters
            body: Request body
            
        Returns:
            Dict with authentication headers
        """
        timestamp = str(int(time.time()))
        
        # Create signature payload
        hashed_payload = hashlib.sha512(body.encode()).hexdigest()
        sign_string = f"{method}\n{url_path}\n{query_string}\n{hashed_payload}\n{timestamp}"
        
        # Generate signature
        signature = hmac.new(
            self.secret_key.encode(),
            sign_string.encode(),
            hashlib.sha512
        ).hexdigest()
        
        return {
            "KEY": self.api_key,
            "Timestamp": timestamp,
            "SIGN": signature,
            "Content-Type": "application/json"
        }
    
    async def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Dict:
        """
        Make HTTP request with exponential backoff retry logic.
        
        Args:
            method: HTTP method
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data
            
        Returns:
            API response as dict
            
        Raises:
            Exception: After max retries exceeded
        """
        url = f"{self.base_url}{endpoint}"
        query_string = "&".join([f"{k}={v}" for k, v in (params or {}).items()])
        body = ""
        if data:
            import json
            body = json.dumps(data)
        
        for attempt in range(self.max_retries):
            try:
                # Generate authentication headers
                headers = self._generate_signature(
                    method.upper(),
                    endpoint,
                    query_string,
                    body
                )
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    if method.upper() == "GET":
                        response = await client.get(url, params=params, headers=headers)
                    elif method.upper() == "POST":
                        response = await client.post(url, params=params, json=data, headers=headers)
                    elif method.upper() == "DELETE":
                        response = await client.delete(url, params=params, headers=headers)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")
                    
                    response.raise_for_status()
                    return response.json()
                    
            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"Gate.io API error (attempt {attempt + 1}/{self.max_retries}): "
                    f"{e.response.status_code} - {e.response.text}"
                )
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff: delay_n = base_delay * 2^n
                    delay = self.base_retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Max retries exceeded for {endpoint}")
                    raise
                    
            except Exception as e:
                logger.error(f"Unexpected error calling {endpoint}: {e}")
                if attempt < self.max_retries - 1:
                    delay = self.base_retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                else:
                    raise
    
    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None
    ) -> Dict:
        """
        Execute real order on Gate.io testnet.
        
        Args:
            symbol: Trading pair (e.g., "BTC_USDT")
            side: "buy" or "sell"
            order_type: "limit" or "market"
            quantity: Order quantity
            price: Limit price (required for limit orders)
            
        Returns:
            Order creation response with order_id and status
        """
        endpoint = "/spot/orders"
        
        order_data = {
            "currency_pair": symbol,
            "side": side.lower(),
            "type": order_type.lower(),
            "amount": str(quantity)
        }
        
        if order_type.lower() == "limit":
            if price is None:
                raise ValueError("Price required for limit orders")
            order_data["price"] = str(price)
        
        logger.info(f"Creating {side} {order_type} order: {symbol} qty={quantity} price={price}")
        
        result = await self._request_with_retry("POST", endpoint, data=order_data)
        
        logger.info(f"Order created: {result.get('id', 'unknown')} status={result.get('status', 'unknown')}")
        return result
    
    async def get_order_status(self, order_id: str, symbol: str) -> Dict:
        """
        Query order execution status.
        
        Args:
            order_id: Order ID from create_order
            symbol: Trading pair
            
        Returns:
            Order status details
        """
        endpoint = f"/spot/orders/{order_id}"
        params = {"currency_pair": symbol}
        
        result = await self._request_with_retry("GET", endpoint, params=params)
        
        logger.debug(f"Order {order_id} status: {result.get('status', 'unknown')}")
        return result
    
    async def get_account_balance(self) -> Dict:
        """
        Fetch testnet account balance.
        
        Returns:
            Dict with balances for all currencies
        """
        endpoint = "/spot/accounts"
        
        result = await self._request_with_retry("GET", endpoint)
        
        # Convert list to dict for easier access
        balances = {item['currency']: item for item in result}
        
        logger.debug(f"Account balances fetched: {len(balances)} currencies")
        return balances
    
    async def fetch_ticker(self, symbol: str) -> Dict:
        """
        Get real-time testnet market data.
        
        Args:
            symbol: Trading pair
            
        Returns:
            Ticker data with last price, volume, etc.
        """
        endpoint = "/spot/tickers"
        params = {"currency_pair": symbol}
        
        result = await self._request_with_retry("GET", endpoint, params=params)
        
        if isinstance(result, list) and len(result) > 0:
            ticker = result[0]
        else:
            ticker = result
        
        logger.debug(f"Ticker {symbol}: last={ticker.get('last', 'N/A')}")
        return ticker
    
    async def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """
        Cancel an open order.
        
        Args:
            order_id: Order ID to cancel
            symbol: Trading pair
            
        Returns:
            Cancellation response
        """
        endpoint = f"/spot/orders/{order_id}"
        params = {"currency_pair": symbol}
        
        result = await self._request_with_retry("DELETE", endpoint, params=params)
        
        logger.info(f"Order {order_id} cancelled")
        return result
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """
        Get all open orders.
        
        Args:
            symbol: Optional trading pair filter
            
        Returns:
            List of open orders
        """
        endpoint = "/spot/orders"
        params = {"status": "open"}
        
        if symbol:
            params["currency_pair"] = symbol
        
        result = await self._request_with_retry("GET", endpoint, params=params)
        
        logger.debug(f"Open orders: {len(result)}")
        return result
    
    async def get_trade_history(self, symbol: str, limit: int = 100) -> List[Dict]:
        """
        Get trade history for a symbol.
        
        Args:
            symbol: Trading pair
            limit: Max number of trades to return
            
        Returns:
            List of historical trades
        """
        endpoint = "/spot/my_trades"
        params = {
            "currency_pair": symbol,
            "limit": limit
        }
        
        result = await self._request_with_retry("GET", endpoint, params=params)
        
        logger.debug(f"Trade history {symbol}: {len(result)} trades")
        return result
