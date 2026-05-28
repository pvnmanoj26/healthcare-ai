import sys

print("Verifying runners imports...")
success = True

try:
    import runners.run_agent
    print("✅ runners.run_agent imported successfully!")
except Exception as e:
    print("❌ runners.run_agent import failed:", e)
    success = False

try:
    import runners.run_ingestion
    print("✅ runners.run_ingestion imported successfully!")
except Exception as e:
    print("❌ runners.run_ingestion import failed:", e)
    success = False

try:
    import runners.run_api
    print("✅ runners.run_api imported successfully!")
except Exception as e:
    print("❌ runners.run_api import failed:", e)
    success = False

try:
    import runners.run_app
    print("✅ runners.run_app imported successfully!")
except Exception as e:
    print("❌ runners.run_app import failed:", e)
    success = False

if success:
    print("🎉 All runner imports checked successfully!")
    sys.exit(0)
else:
    print("❌ Some imports failed.")
    sys.exit(1)
