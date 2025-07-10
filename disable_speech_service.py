#!/usr/bin/env python3
"""
Quick script to disable speech service for immediate performance relief
"""

import os
import sys

def disable_speech_service():
    """Disable speech service by setting environment variables"""
    
    # Environment variables to disable speech service
    env_vars = {
        "DISABLE_SPEECH_SERVICE": "true",
        "DISABLE_SPEECH_ON_HIGH_CPU": "true",
        "CPU_THRESHOLD_FOR_SPEECH_DISABLE": "50.0"  # Lower threshold for immediate effect
    }
    
    print("🚨 Disabling speech service for immediate performance relief...")
    print("=" * 60)
    
    # Check current environment
    current_disable = os.getenv("DISABLE_SPEECH_SERVICE", "false")
    current_cpu_disable = os.getenv("DISABLE_SPEECH_ON_HIGH_CPU", "false")
    
    print(f"Current settings:")
    print(f"  DISABLE_SPEECH_SERVICE: {current_disable}")
    print(f"  DISABLE_SPEECH_ON_HIGH_CPU: {current_cpu_disable}")
    print()
    
    # Set environment variables
    for key, value in env_vars.items():
        os.environ[key] = value
        print(f"✅ Set {key}={value}")
    
    print()
    print("🎯 Speech service will be disabled on next application restart")
    print()
    print("To apply immediately, restart your application:")
    print("  docker-compose restart b2b-sales-backend")
    print("  # or")
    print("  python main.py")
    print()
    print("To re-enable speech service later, set:")
    print("  DISABLE_SPEECH_SERVICE=false")
    print("  DISABLE_SPEECH_ON_HIGH_CPU=false")

def show_performance_tips():
    """Show additional performance optimization tips"""
    
    print("💡 Additional Performance Optimization Tips:")
    print("=" * 60)
    
    tips = [
        "1. Reduce AI response length: Set AI_MAX_TOKENS=300",
        "2. Increase cache TTL: Set CACHE_TTL=600 (10 minutes)",
        "3. Disable hybrid retriever: Set USE_HYBRID_RETRIEVER=false",
        "4. Reduce database pool size: Set DATABASE_POOL_SIZE=10",
        "5. Increase request timeout: Set REQUEST_TIMEOUT=60",
        "6. Disable complex flow analysis: Set ENABLE_COMPLEX_FLOW_ANALYSIS=false",
        "7. Use smaller Whisper model: Set WHISPER_MODEL=tiny",
        "8. Reduce Elasticsearch heap: Set ES_JAVA_OPTS='-Xms512m -Xmx1g'"
    ]
    
    for tip in tips:
        print(f"   {tip}")
    
    print()
    print("🔧 Quick environment variable setup:")
    print("export DISABLE_SPEECH_SERVICE=true")
    print("export AI_MAX_TOKENS=300")
    print("export CACHE_TTL=600")
    print("export USE_HYBRID_RETRIEVER=false")
    print("export DATABASE_POOL_SIZE=10")
    print("export REQUEST_TIMEOUT=60")

def check_current_performance():
    """Check current performance settings"""
    
    print("🔍 Current Performance Settings:")
    print("=" * 60)
    
    settings = {
        "DISABLE_SPEECH_SERVICE": os.getenv("DISABLE_SPEECH_SERVICE", "false"),
        "DISABLE_SPEECH_ON_HIGH_CPU": os.getenv("DISABLE_SPEECH_ON_HIGH_CPU", "false"),
        "CPU_THRESHOLD_FOR_SPEECH_DISABLE": os.getenv("CPU_THRESHOLD_FOR_SPEECH_DISABLE", "80.0"),
        "AI_MAX_TOKENS": os.getenv("AI_MAX_TOKENS", "1000"),
        "CACHE_TTL": os.getenv("CACHE_TTL", "300"),
        "USE_HYBRID_RETRIEVER": os.getenv("USE_HYBRID_RETRIEVER", "true"),
        "DATABASE_POOL_SIZE": os.getenv("DATABASE_POOL_SIZE", "20"),
        "REQUEST_TIMEOUT": os.getenv("REQUEST_TIMEOUT", "30"),
        "ENABLE_RESPONSE_CACHING": os.getenv("ENABLE_RESPONSE_CACHING", "true")
    }
    
    for key, value in settings.items():
        status = "✅" if value.lower() in ["true", "1", "yes"] else "❌" if value.lower() in ["false", "0", "no"] else "ℹ️"
        print(f"   {status} {key}: {value}")
    
    print()
    print("🎯 Performance Status:")
    
    # Analyze settings
    speech_disabled = settings["DISABLE_SPEECH_SERVICE"].lower() == "true"
    cpu_monitoring = settings["DISABLE_SPEECH_ON_HIGH_CPU"].lower() == "true"
    caching_enabled = settings["ENABLE_RESPONSE_CACHING"].lower() == "true"
    hybrid_disabled = settings["USE_HYBRID_RETRIEVER"].lower() == "false"
    
    if speech_disabled:
        print("   ✅ Speech service is disabled")
    elif cpu_monitoring:
        print("   ⚠️  Speech service will be disabled when CPU > 80%")
    else:
        print("   ❌ Speech service is enabled (may cause high CPU usage)")
    
    if caching_enabled:
        print("   ✅ Response caching is enabled")
    else:
        print("   ❌ Response caching is disabled")
    
    if hybrid_disabled:
        print("   ✅ Hybrid retriever is disabled (better performance)")
    else:
        print("   ⚠️  Hybrid retriever is enabled (may use more resources)")

def main():
    """Main function"""
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "disable":
            disable_speech_service()
        elif command == "tips":
            show_performance_tips()
        elif command == "check":
            check_current_performance()
        else:
            print(f"Unknown command: {command}")
            print("Available commands: disable, tips, check")
    else:
        print("🚀 B2B Sales Backend Performance Optimizer")
        print("=" * 60)
        print()
        print("Available commands:")
        print("  python disable_speech_service.py disable  - Disable speech service")
        print("  python disable_speech_service.py tips     - Show performance tips")
        print("  python disable_speech_service.py check    - Check current settings")
        print()
        check_current_performance()

if __name__ == "__main__":
    main() 