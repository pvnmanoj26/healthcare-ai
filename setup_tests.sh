#!/bin/bash
set -e

mkdir -p tests

echo "Creating tests/test_models.py..."
cat > tests/test_models.py << 'INNER_EOF'
from models.patient import PatientDemographics
from models.events import ClinicalEvent

def test_patient_demographics():
    patient = PatientDemographics(
        patient_id="123",
        first_name="John",
        last_name="Doe",
        gender="M",
        birthdate="1980-01-01"
    )
    assert patient.patient_id == "123"
    assert patient.first_name == "John"
    print("test_patient_demographics passed!")

def test_clinical_event():
    event = ClinicalEvent(
        patient_id="123",
        event_type="conditions",
        event_date="2026-05-28",
        description="Type 2 Diabetes"
    )
    assert event.event_type == "conditions"
    assert event.description == "Type 2 Diabetes"
    print("test_clinical_event passed!")

if __name__ == "__main__":
    test_patient_demographics()
    test_clinical_event()
    print("All model tests passed!")
INNER_EOF

echo "Creating tests/test_adapters.py..."
cat > tests/test_adapters.py << 'INNER_EOF'
from adapters.vertex_ai import _initialized as vertex_init
from adapters.anthropic import DEFAULT_MODEL

def test_adapters_imports():
    assert not vertex_init  # Starts uninitialized
    assert isinstance(DEFAULT_MODEL, str)
    print("test_adapters_imports passed!")

if __name__ == "__main__":
    test_adapters_imports()
    print("All adapter tests passed!")
INNER_EOF

echo "Creating tests/test_tools.py..."
cat > tests/test_tools.py << 'INNER_EOF'
from tools.csv_tools import detect_csv_category

def test_detect_csv_category():
    assert detect_csv_category("patients.csv") == "patients"
    assert detect_csv_category("medications.csv") == "medications"
    assert detect_csv_category("conditions.csv") == "conditions"
    print("test_detect_csv_category passed!")

if __name__ == "__main__":
    test_detect_csv_category()
    print("All tool tests passed!")
INNER_EOF

echo "Automated tests created successfully!"

echo "Running tests..."
python tests/test_models.py
python tests/test_adapters.py
python tests/test_tools.py
print("🎉 All automated unit tests executed successfully!")
