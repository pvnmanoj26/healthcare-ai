from tools.csv_tools import detect_csv_category

def test_detect_csv_category():
    assert detect_csv_category("patients.csv") == "patients"
    assert detect_csv_category("medications.csv") == "medications"
    assert detect_csv_category("conditions.csv") == "conditions"
    print("test_detect_csv_category passed!")

if __name__ == "__main__":
    test_detect_csv_category()
    print("All tool tests passed!")
