import json
from pathlib import Path
from typing import List, Dict, Tuple
import random
import os

def load_product_data() -> Dict[str, List[Dict]]:
    product_data = {}
    json_dir = Path("Data/json")
    
    for json_file in json_dir.glob("*.json"):
        category = json_file.stem
        with open(json_file, 'r') as f:
            try:
                products = json.load(f)
                product_data[category] = products
                print(f"Loaded {len(products)} products from {category}")
            except json.JSONDecodeError:
                print(f"Error loading {json_file}")
                continue
    
    return product_data

def generate_query_patterns() -> List[Tuple[str, str]]:
    """Generate different query patterns for testing retrieval"""
    return [
        ("specific_feature", "What {product} options do you have with {feature}?"),
        ("comparison", "How does {product1} compare to {product2} in terms of {feature}?"),
        ("requirement", "I need a {product} that can handle {requirement}. What do you recommend?"),
        ("specification", "Do you have any {product} with {spec}?"),
        ("use_case", "What {product} would be best for {use_case}?"),
        ("budget", "What are your {product} options under {budget}?"),
        ("compatibility", "Will {product1} work with {product2}?"),
        ("performance", "How well does {product} perform for {task}?"),
        ("upgrade", "What {product} would be a good upgrade from {current_product}?"),
        ("combination", "I need a system with {product1} and {product2} for {use_case}.")
    ]

def get_default_features(category: str) -> Dict[str, str]:
    """Get default features for a category if none are found in the product data"""
    default_features = {
        "cpu": {
            "cores": "multiple",
            "threads": "high",
            "base_clock": "fast",
            "boost_clock": "fast",
            "tdp": "standard",
            "socket": "standard"
        },
        "gpu": {
            "memory": "high",
            "boost_clock": "fast",
            "ports": "multiple",
            "tdp": "standard",
            "length": "standard"
        },
        "memory": {
            "speed": "fast",
            "capacity": "large",
            "type": "DDR4",
            "cas_latency": "low",
            "voltage": "standard"
        },
        "storage": {
            "capacity": "large",
            "interface": "fast",
            "cache": "large",
            "form_factor": "standard",
            "type": "SSD"
        },
        "motherboard": {
            "chipset": "high-end",
            "socket": "standard",
            "memory_slots": "multiple",
            "expansion_slots": "multiple",
            "form_factor": "standard"
        },
        "power-supply": {
            "wattage": "high",
            "efficiency": "high",
            "modular": "yes",
            "connectors": "multiple",
            "protection": "comprehensive"
        },
        "case": {
            "form_factor": "standard",
            "expansion_slots": "multiple",
            "cooling": "efficient",
            "material": "premium",
            "design": "modern"
        }
    }
    
    # Generic features for any category
    generic_features = {
        "quality": "high",
        "performance": "excellent",
        "reliability": "high",
        "compatibility": "broad",
        "features": "comprehensive"
    }
    
    return default_features.get(category, generic_features)

def extract_product_features(product: Dict, category: str) -> Dict[str, str]:
    """Extract relevant features based on product category"""
    features = {}
    default_features = get_default_features(category)
    
    # Try to get features from product data
    for feature in default_features.keys():
        if feature in product:
            features[feature] = str(product[feature])
    
    # If no features were found, use defaults
    if not features:
        print(f"No features found for {category}, using defaults")
        features = default_features
    
    return features

def generate_test_cases() -> List[Dict]:
    # Load product data
    product_data = load_product_data()
    query_patterns = generate_query_patterns()
    
    # Define company sizes and industries
    company_sizes = ["startup", "small", "medium", "large", "enterprise"]
    industries = [
        "technology", "healthcare", "finance", "manufacturing", "retail",
        "education", "creative_services", "gaming", "data_center"
    ]
    
    test_cases = []
    
    # Generate test cases for each product category
    for category, products in product_data.items():
        if not products:
            print(f"No products found for category: {category}")
            continue
        
        print(f"\nProcessing category: {category}")
        print(f"Number of products: {len(products)}")
        
        # Get multiple sample products for comparison and combination queries
        sample_products = random.sample(products, min(3, len(products)))
        
        # Generate 3-5 test cases per category
        for i in range(random.randint(3, 5)):
            company_size = random.choice(company_sizes)
            industry = random.choice(industries)
            query_pattern, template = random.choice(query_patterns)
            
            # Select products for the query
            product1 = random.choice(sample_products)
            product2 = random.choice(sample_products) if len(sample_products) > 1 else product1
            
            # Extract features for ground truth
            features1 = extract_product_features(product1, category)
            features2 = extract_product_features(product2, category)
            
            print(f"\nTest case {i+1} for {category}:")
            print(f"Product 1 features: {features1}")
            print(f"Product 2 features: {features2}")
            
            # Ensure we have features to work with
            if not features1:
                print(f"Warning: No features found for product1 in {category}, using defaults")
                features1 = get_default_features(category)
            if not features2:
                print(f"Warning: No features found for product2 in {category}, using defaults")
                features2 = get_default_features(category)
            
            # Generate question based on query pattern
            if query_pattern == "specific_feature":
                feature = random.choice(list(features1.keys()))
                question = template.format(
                    product=category.replace('-', ' '),
                    feature=feature
                )
                ground_truth = f"Our {product1.get('name', 'professional')} {category.replace('-', ' ')} features {feature} of {features1[feature]}, making it suitable for {industry} applications."
            
            elif query_pattern == "comparison":
                feature = random.choice(list(features1.keys()))
                question = template.format(
                    product1=category.replace('-', ' '),
                    product2=category.replace('-', ' '),
                    feature=feature
                )
                ground_truth = f"When comparing {product1.get('name', 'Model A')} and {product2.get('name', 'Model B')}, {product1.get('name')} offers {features1[feature]} {feature} while {product2.get('name')} provides {features2[feature]} {feature}."
            
            elif query_pattern == "requirement":
                feature = random.choice(list(features1.keys()))
                question = template.format(
                    product=category.replace('-', ' '),
                    requirement=f"{features1[feature]} {feature}"
                )
                ground_truth = f"For your requirement of {features1[feature]} {feature}, we recommend our {product1.get('name', 'professional')} {category.replace('-', ' ')}. It's specifically designed to handle such {industry} workloads."
            
            elif query_pattern == "specification":
                feature = random.choice(list(features1.keys()))
                question = template.format(
                    product=category.replace('-', ' '),
                    spec=f"{features1[feature]} {feature}"
                )
                ground_truth = f"Yes, our {product1.get('name', 'professional')} {category.replace('-', ' ')} meets your specification with {features1[feature]} {feature}. It's particularly well-suited for {industry} applications."
            
            elif query_pattern == "use_case":
                question = template.format(
                    product=category.replace('-', ' '),
                    use_case=f"{industry} {random.choice(['workloads', 'applications', 'requirements'])}"
                )
                ground_truth = f"For {industry} {random.choice(['workloads', 'applications', 'requirements'])}, our {product1.get('name', 'professional')} {category.replace('-', ' ')} is ideal. It features {', '.join(f'{k}: {v}' for k, v in list(features1.items())[:3])}."
            
            elif query_pattern == "combination":
                question = template.format(
                    product1=category.replace('-', ' '),
                    product2=random.choice(list(product_data.keys())).replace('-', ' '),
                    use_case=f"{industry} {random.choice(['workloads', 'applications', 'requirements'])}"
                )
                ground_truth = f"For your {industry} needs, we recommend combining our {product1.get('name', 'professional')} {category.replace('-', ' ')} with compatible components. The {category.replace('-', ' ')} features {', '.join(f'{k}: {v}' for k, v in list(features1.items())[:3])}."
            
            else:
                feature = random.choice(list(features1.keys()))
                question = template.format(
                    product=category.replace('-', ' '),
                    feature=feature
                )
                ground_truth = f"Our {product1.get('name', 'professional')} {category.replace('-', ' ')} is designed for {industry} applications, featuring {', '.join(f'{k}: {v}' for k, v in list(features1.items())[:3])}."
            
            test_case = {
                "question": question,
                "ground_truth": ground_truth,
                "customer_context": {
                    "company_size": company_size,
                    "industry": industry,
                    "use_case": f"{category}_requirements"
                },
                "expected_stage": "solution_presentation",
                "query_type": query_pattern,
                "product_category": category,
                "relevant_features": list(features1.keys())
            }
            
            test_cases.append(test_case)
    
    return test_cases

def main():
    # Generate test cases
    test_cases = generate_test_cases()
    
    # Create output directory if it doesn't exist
    output_dir = Path("Data")
    output_dir.mkdir(exist_ok=True)
    
    # Save test cases to file
    output_file = output_dir / "test_cases.json"
    with open(output_file, 'w') as f:
        json.dump({"test_cases": test_cases}, f, indent=4)
    
    print(f"\nGenerated {len(test_cases)} test cases and saved to {output_file}")
    
    # Print sample of generated test cases
    print("\nSample Test Cases:")
    print("=================")
    for i, case in enumerate(test_cases[:3]):
        print(f"\nTest Case {i+1}:")
        print(f"Question: {case['question']}")
        print(f"Ground Truth: {case['ground_truth']}")
        print(f"Query Type: {case['query_type']}")
        print(f"Product Category: {case['product_category']}")
        print(f"Relevant Features: {case['relevant_features']}")

if __name__ == "__main__":
    main() 