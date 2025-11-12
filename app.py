from flask import Flask, request
import json
import random
import re
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()
app = Flask(__name__)

class MongoDBManager:
    def __init__(self):
        try:
            self.client = MongoClient(os.getenv('MONGODB_URI'))
            self.db = self.client[os.getenv('DATABASE_NAME', 'semantic_search')]
            self.products = self.db['products']
            self.searches = self.db['search_history']
            self.client.admin.command('ping')
            self.connected = True
        except Exception as e:
            self.connected = False
            self.error = str(e)
    
    def setup_indexes(self):
        if self.connected:
            try:
                self.products.create_index([("name", "text"), ("description", "text")])
                return True
            except:
                return False
        return False
    
    def insert_product(self, product_data):
        if self.connected:
            return self.products.insert_one(product_data)
        return None
    
    def search_products(self, query):
        if not self.connected:
            return []
        try:
            results = list(self.products.find({
                "$or": [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                    {"category": {"$regex": query, "$options": "i"}}
                ]
            }).limit(15))
            return results
        except:
            return []
    
    def log_search(self, query, results_count):
        if self.connected:
            try:
                self.searches.insert_one({
                    "query": query,
                    "results_count": results_count,
                    "timestamp": {"$currentDate": True}
                })
            except:
                pass
    
    def get_product_count(self):
        if self.connected:
            try:
                return self.products.count_documents({})
            except:
                return 0
        return 0

class CurrencyConverter:
    def __init__(self):
        self.rates = {
            'USD': 1.0, 'EUR': 0.85, 'GBP': 0.73, 'JPY': 110.0,
            'CAD': 1.25, 'AUD': 1.35, 'INR': 75.0, 'CNY': 6.5
        }
        self.symbols = {
            'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥',
            'CAD': 'C$', 'AUD': 'A$', 'INR': '₹', 'CNY': '¥'
        }
    
    def convert_price(self, usd_price, target_currency):
        if target_currency not in self.rates:
            return f"${usd_price}"
        
        converted = usd_price * self.rates[target_currency]
        symbol = self.symbols[target_currency]
        
        if target_currency in ['JPY', 'INR']:
            return f"{symbol}{int(converted)}"
        else:
            return f"{symbol}{converted:.2f}"

class SemanticAI:
    def __init__(self):
        self.semantic_mappings = {
            'purchase_intent': ['buy', 'purchase', 'get', 'need', 'want', 'looking for', 'shopping for', 'find me'],
            'comparison_intent': ['compare', 'vs', 'versus', 'difference', 'better', 'best between'],
            'recommendation_intent': ['recommend', 'suggest', 'advice', 'what should', 'help me choose'],
            
            'mobile_device': ['phone', 'smartphone', 'mobile', 'cell phone', 'iphone', 'android', 'device'],
            'computer': ['laptop', 'notebook', 'computer', 'macbook', 'pc', 'workstation', 'ultrabook'],
            'audio_device': ['headphones', 'earbuds', 'headset', 'speakers', 'audio', 'sound'],
            
            'premium_quality': ['premium', 'high-end', 'luxury', 'professional', 'top-tier', 'flagship', 'pro'],
            'budget_friendly': ['cheap', 'budget', 'affordable', 'economical', 'value', 'low-cost', 'inexpensive'],
            'mid_range': ['mid-range', 'moderate', 'decent', 'good', 'standard', 'average'],
            
            'photography': ['camera', 'photo', 'photography', 'pictures', 'selfie', 'portrait', 'video recording'],
            'productivity': ['work', 'office', 'business', 'productivity', 'professional', 'coding', 'programming'],
            'entertainment': ['gaming', 'movies', 'music', 'streaming', 'entertainment', 'media', 'fun'],
            'fitness': ['fitness', 'workout', 'exercise', 'running', 'sports', 'health', 'tracking'],
            'travel': ['travel', 'portable', 'lightweight', 'compact', 'on-the-go', 'mobile']
        }
    
    def extract_semantic_meaning(self, query):
        query_lower = query.lower()
        
        intent = 'search'
        for intent_type, keywords in self.semantic_mappings.items():
            if intent_type.endswith('_intent') and any(keyword in query_lower for keyword in keywords):
                intent = intent_type.replace('_intent', '')
                break
        
        category = None
        for cat_type, keywords in self.semantic_mappings.items():
            if not cat_type.endswith('_intent') and not cat_type.endswith('_quality') and any(keyword in query_lower for keyword in keywords):
                category = cat_type
                break
        
        quality = 'mid_range'
        for quality_type, keywords in self.semantic_mappings.items():
            if quality_type.endswith('_quality') and any(keyword in query_lower for keyword in keywords):
                quality = quality_type
                break
        
        use_case = None
        use_cases = ['photography', 'productivity', 'entertainment', 'fitness', 'travel']
        for case in use_cases:
            if case in self.semantic_mappings and any(keyword in query_lower for keyword in self.semantic_mappings[case]):
                use_case = case
                break
        
        price_constraint = None
        price_match = re.search(r'under \$?(\d+)', query_lower)
        if price_match:
            price_constraint = int(price_match.group(1))
        
        return {
            'intent': intent,
            'category': category,
            'quality': quality,
            'use_case': use_case,
            'price_constraint': price_constraint,
            'original_query': query
        }
    
    def generate_semantic_response(self, semantic_data):
        intent = semantic_data['intent']
        category = semantic_data['category']
        quality = semantic_data['quality']
        use_case = semantic_data['use_case']
        price_constraint = semantic_data['price_constraint']
        
        response_parts = []
        
        if intent == 'recommendation':
            response_parts.append(" **Based on your request, here are my top recommendations:**")
        elif intent == 'comparison':
            response_parts.append(" **Here's what I found for comparison:**")
        else:
            response_parts.append(" **Semantic Analysis Results:**")
        
        quality_advice = {
            'premium_quality': " **Premium Choice**: Expect top-tier performance, build quality, and latest features",
            'budget_friendly': " **Budget Smart**: Great value options that don't compromise on essentials",
            'mid_range': " **Balanced Option**: Perfect mix of features and affordability"
        }
        
        if quality in quality_advice:
            response_parts.append(f"\n{quality_advice[quality]}")
        
        if price_constraint:
            response_parts.append(f"\n **Budget Constraint**: Under ${price_constraint} - I'll prioritize value and essential features")
        
        return "\n".join(response_parts)

# Initialize components
mongo_db = MongoDBManager()
semantic_ai = SemanticAI()
currency_converter = CurrencyConverter()

@app.route('/')
def home():
    return '''
<!DOCTYPE html>
<html>
<head>
    <title>AI-Assisted Semantic Search Engine</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; background: white; border-radius: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.1); overflow: hidden; }
        .header { background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); padding: 40px; text-align: center; color: white; }
        .header h1 { font-size: 2.5rem; margin-bottom: 10px; }
        .search-section { padding: 40px; }
        .search-box { display: flex; gap: 10px; margin-bottom: 20px; }
        .search-input { flex: 1; padding: 15px; border: 2px solid #e5e7eb; border-radius: 10px; font-size: 16px; }
        .search-btn { padding: 15px 30px; background: #4f46e5; color: white; border: none; border-radius: 10px; cursor: pointer; }
        .ai-btn { padding: 15px 30px; background: #0ea5e9; color: white; border: none; border-radius: 10px; cursor: pointer; }
        .add-btn { padding: 15px 30px; background: #059669; color: white; border: none; border-radius: 10px; cursor: pointer; }
        .currency-select { padding: 15px; border: 2px solid #e5e7eb; border-radius: 10px; background: white; min-width: 120px; }
        .results { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .product { background: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 4px solid #4f46e5; }
        .product-name { font-weight: bold; font-size: 1.1rem; margin-bottom: 10px; }
        .product-desc { color: #666; margin-bottom: 15px; }
        .product-footer { display: flex; justify-content: space-between; align-items: center; }
        .product-price { font-weight: bold; color: #059669; font-size: 1.2rem; }
        .source-badge { background: #e5e7eb; padding: 4px 8px; border-radius: 15px; font-size: 0.8rem; }
        .db-badge { background: #10b981 !important; color: white !important; padding: 4px 8px; border-radius: 15px; font-weight: bold; }
        .visit-btn { background: #059669; color: white; padding: 8px 16px; border-radius: 5px; text-decoration: none; }
        .status-info { background: #f0f9ff; border: 1px solid #0ea5e9; border-radius: 10px; padding: 15px; margin-bottom: 20px; }
        .ai-recommendation { background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); border: 2px solid #0ea5e9; border-radius: 15px; padding: 25px; margin-bottom: 30px; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 AI-Assisted Semantic Search Engine</h1>
            <p>Intelligent product discovery powered by AI and MongoDB</p>
        </div>
        <div class="search-section">
            <div class="ai-recommendation" id="aiRecommendation">
                <h3>🤖 AI Assistant</h3>
                <div class="content" id="aiContent"></div>
            </div>
            
            <div id="statusInfo" class="status-info"></div>
            
            <div class="search-box">
                <input type="text" id="searchInput" class="search-input" placeholder="Search: iPhone, laptop, headphones...">
                <select id="currencySelect" class="currency-select">
                    <option value="USD">USD ($)</option>
                    <option value="EUR">EUR (€)</option>
                    <option value="GBP">GBP (£)</option>
                    <option value="JPY">JPY (¥)</option>
                    <option value="CAD">CAD (C$)</option>
                    <option value="AUD">AUD (A$)</option>
                    <option value="INR">INR (₹)</option>
                    <option value="CNY">CNY (¥)</option>
                </select>
                <button onclick="getAIRecommendation()" class="ai-btn">Ask AI</button>
                <button onclick="search()" class="search-btn">Search</button>
                <button onclick="addData()" class="add-btn">Add Data</button>
            </div>
            <div id="results" class="results"></div>
        </div>
    </div>

    <script>
        function search() {
            const query = document.getElementById('searchInput').value.trim();
            const currency = document.getElementById('currencySelect').value;
            if (!query) return;
            
            document.getElementById('results').innerHTML = '<div style="text-align:center;padding:40px;">Searching...</div>';
            
            fetch(`/search?q=${encodeURIComponent(query)}&currency=${currency}`)
                .then(response => response.text())
                .then(html => {
                    document.getElementById('results').innerHTML = html;
                });
        }
        
        function getAIRecommendation() {
            const query = document.getElementById('searchInput').value.trim();
            if (!query) return;
            
            const aiDiv = document.getElementById('aiRecommendation');
            const aiContent = document.getElementById('aiContent');
            
            aiDiv.style.display = 'block';
            aiContent.innerHTML = '🤔 Analyzing your request...';
            
            fetch('/ai-recommend?q=' + encodeURIComponent(query))
                .then(response => response.text())
                .then(recommendation => {
                    aiContent.innerHTML = recommendation;
                    setTimeout(() => search(), 1000);
                });
        }
        
        function addData() {
            fetch('/add-data')
                .then(response => response.text())
                .then(result => {
                    alert(result);
                    checkStatus();
                });
        }
        
        function checkStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    const statusDiv = document.getElementById('statusInfo');
                    if (data.connected) {
                        statusDiv.innerHTML = `🟢 MongoDB Connected | Products: ${data.product_count}`;
                        statusDiv.style.background = '#f0fdf4';
                    } else {
                        statusDiv.innerHTML = `🟡 MongoDB Disconnected | Using fallback data`;
                        statusDiv.style.background = '#fef2f2';
                    }
                });
        }
        
        window.onload = checkStatus;
        
        document.getElementById('searchInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') search();
        });
    </script>
</body>
</html>
'''

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    currency = request.args.get('currency', 'USD')
    if not query:
        return '<div>Please enter a search term</div>'
    
    semantic_data = semantic_ai.extract_semantic_meaning(query)
    quality = semantic_data['quality']
    
    results = []
    
    # Search MongoDB or use fallback
    if mongo_db.connected:
        db_results = mongo_db.search_products(query)
        mongo_db.log_search(query, len(db_results))
        
        for product in db_results:
            converted_price = currency_converter.convert_price(product['price'], currency)
            results.append({
                'name': product['name'],
                'desc': product['description'],
                'price': converted_price,
                'source': 'MongoDB Atlas',
                'url': f"https://www.google.com/search?q={query.replace(' ', '+')}+{product['name'].replace(' ', '+')}",
                'is_db': True
            })
    else:
        # Fallback data
        mock_products = [
            {"name": "iPhone 15 Pro Max", "description": "Latest Apple smartphone", "price": 1199},
            {"name": "MacBook Pro M3", "description": "Professional laptop", "price": 1999},
            {"name": "Sony WH-1000XM5", "description": "Noise canceling headphones", "price": 399}
        ]
        
        for product in mock_products:
            if query.lower() in product['name'].lower():
                converted_price = currency_converter.convert_price(product['price'], currency)
                results.append({
                    'name': product['name'],
                    'desc': product['description'],
                    'price': converted_price,
                    'source': 'Local Database',
                    'url': f"https://www.google.com/search?q={query.replace(' ', '+')}",
                    'is_db': True
                })
    
    # Add external results
    external_sources = [
        ('Google', f'https://www.google.com/search?tbm=shop&q={query.replace(" ", "+")}'),
        ('Amazon', f'https://www.amazon.com/s?k={query.replace(" ", "+")}'),
        ('Bing', f'https://www.bing.com/search?q={query.replace(" ", "+")}+buy')
    ]
    
    for source, url in external_sources:
        price_ranges = {'premium_quality': (600, 1500), 'mid_range': (200, 600), 'budget_friendly': (50, 200)}
        price_min, price_max = price_ranges.get(quality, (100, 500))
        
        usd_price = random.randint(price_min, price_max) + 0.99
        converted_price = currency_converter.convert_price(usd_price, currency)
        
        results.append({
            'name': f'{query} - {source} Result',
            'desc': f'External result from {source}',
            'price': converted_price,
            'source': source,
            'url': url,
            'is_db': False
        })
    
    # Generate HTML
    html = ''
    for product in results:
        badge_class = 'db-badge' if product.get('is_db') else 'source-badge'
        html += f'''
        <div class="product">
            <div class="product-name">{product['name']}</div>
            <div class="product-desc">{product['desc']}</div>
            <div class="product-footer">
                <div class="product-price">{product['price']}</div>
                <span class="{badge_class}">{product['source']}</span>
                <a href="{product['url']}" target="_blank" class="visit-btn">Visit</a>
            </div>
        </div>
        '''
    
    return html

@app.route('/ai-recommend')
def ai_recommend():
    query = request.args.get('q', '').strip()
    if not query:
        return 'Please enter your search query'
    
    semantic_data = semantic_ai.extract_semantic_meaning(query)
    recommendation = semantic_ai.generate_semantic_response(semantic_data)
    return recommendation

@app.route('/status')
def status():
    return {
        'connected': mongo_db.connected,
        'product_count': mongo_db.get_product_count(),
        'error': getattr(mongo_db, 'error', None) if not mongo_db.connected else None
    }

@app.route('/add-data')
def add_data():
    if not mongo_db.connected:
        return f"MongoDB connection failed. Check your .env file."
    
    sample_products = [
        {"name": "iPhone 15 Pro Max", "description": "Latest Apple smartphone with titanium design", "category": "mobile_device", "quality": "premium_quality", "price": 1199},
        {"name": "Samsung Galaxy S24", "description": "Android flagship with AI features", "category": "mobile_device", "quality": "premium_quality", "price": 999},
        {"name": "MacBook Pro M3", "description": "Professional laptop for developers", "category": "computer", "quality": "premium_quality", "price": 1999},
        {"name": "Sony WH-1000XM5", "description": "Noise canceling headphones", "category": "audio_device", "quality": "premium_quality", "price": 399},
        {"name": "Acer Aspire 5", "description": "Budget laptop for students", "category": "computer", "quality": "budget_friendly", "price": 499}
    ]
    
    try:
        mongo_db.setup_indexes()
        
        existing_count = mongo_db.get_product_count()
        if existing_count > 0:
            return f"Database already has {existing_count} products."
        
        inserted_count = 0
        for product in sample_products:
            result = mongo_db.insert_product(product)
            if result:
                inserted_count += 1
        
        return f"Successfully added {inserted_count} products to MongoDB!"
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == '__main__':
    print('Starting AI-Assisted Semantic Search Engine on http://localhost:5000')
    if mongo_db.connected:
        print('MongoDB connected successfully')
        print(f'Products in database: {mongo_db.get_product_count()}')
    else:
        print('MongoDB connection failed - using fallback data')
    app.run(debug=True, port=5000)

