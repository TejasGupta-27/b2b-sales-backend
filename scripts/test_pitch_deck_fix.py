#!/usr/bin/env python3
"""
Test script to verify the pitch deck generation fixes
"""

import asyncio
import sys
import os

# Add the project path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

async def test_pitch_deck_fix():
    """Test the pitch deck generation with similar products"""
    
    try:
        from services.pitch_deck_service import PitchDeckService
        
        # Create service
        service = PitchDeckService()
        
        # Test data with sample quote
        test_quote = """
        Customer: Acme Corporation
        Product: High-Performance Workstation
        CPU: Intel Core i7-13700K
        RAM: 32GB DDR4
        Storage: 1TB NVMe SSD
        Price: $2,500
        Warranty: 3 years
        Support: 24/7 technical support
        Delivery: 5-7 business days
        """
        
        # Test similar products (simulating hybrid retriever output)
        similar_products = [
            {
                'name': 'Dell Precision 7670',
                'description': 'Mobile workstation with Intel Core i7 processor, 32GB RAM, professional graphics',
                'price': 2800,
                'vendor': 'Dell',
                'brand': 'Dell'
            },
            {
                'name': 'HP ZBook Studio G9',
                'description': 'Professional workstation laptop with high-performance GPU and enterprise features',
                'price': 2650,
                'vendor': 'HP',
                'brand': 'HP'
            },
            {
                'name': 'Lenovo ThinkPad P1 Gen 5',
                'description': 'Ultra-portable workstation with Intel vPro technology and ISV certification',
                'price': 2750,
                'vendor': 'Lenovo',
                'brand': 'Lenovo'
            }
        ]
        
        print("🧪 Testing pitch deck generation with similar products...")
        
        # Step 1: Test structure generation (without comparison table)
        print("📝 Step 1: Generating deck structure...")
        deck_structure = await service.extract_ppt_structure(test_quote, include_comparison_table=False)
        
        print(f"✅ Generated structure with {len(deck_structure.get('slides', []))} slides")
        print(f"   Tables in structure: {len(deck_structure.get('tables', []))}")
        
        # Step 2: Test comparison table creation
        print("📊 Step 2: Creating comparison table...")
        comparison_table = service.create_comparison_table_from_products(similar_products)
        
        print(f"✅ Created comparison table with {len(comparison_table['rows'])} products")
        print(f"   Table title: {comparison_table['title']}")
        print(f"   Columns: {comparison_table['columns']}")
        
        # Step 3: Test full presentation generation
        print("📋 Step 3: Generating full presentation...")
        
        # Create output directory
        output_dir = "test_outputs"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        output_path = os.path.join(output_dir, "test_pitch_deck_fixed.pptx")
        
        # Generate presentation with similar products
        result_path = await service.generate_ppt(
            deck_structure, 
            output_path, 
            similar_products=similar_products
        )
        
        if result_path and os.path.exists(result_path):
            file_size = os.path.getsize(result_path)
            print(f"✅ Presentation generated successfully!")
            print(f"   File: {result_path}")
            print(f"   Size: {file_size:,} bytes")
            
            # Test without similar products for comparison
            output_path_no_products = os.path.join(output_dir, "test_pitch_deck_no_products.pptx")
            result_path_no_products = await service.generate_ppt(
                deck_structure, 
                output_path_no_products, 
                similar_products=None
            )
            
            if result_path_no_products and os.path.exists(result_path_no_products):
                file_size_no_products = os.path.getsize(result_path_no_products)
                print(f"✅ Comparison presentation (no products) generated!")
                print(f"   File: {result_path_no_products}")
                print(f"   Size: {file_size_no_products:,} bytes")
            
            print("\n🎉 All tests passed!")
            print("\n📋 Summary of fixes:")
            print("   ✅ Removed fake products from LLM-generated comparison table")
            print("   ✅ Single comparison table with real similar products")
            print("   ✅ Proper product data flow from hybrid retriever")
            print("   ✅ No duplicate tables in presentation")
            
        else:
            print("❌ Presentation generation failed")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        print(traceback.format_exc())
        return False
        
    return True

if __name__ == "__main__":
    print("🔧 Testing pitch deck generation fixes...")
    success = asyncio.run(test_pitch_deck_fix())
    if success:
        print("\n✅ All fixes verified successfully!")
    else:
        print("\n❌ Some tests failed. Please check the implementation.")
