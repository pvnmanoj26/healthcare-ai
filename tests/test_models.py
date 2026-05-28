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
        source_file="conditions.csv",
        description="Type 2 Diabetes",
        code="E11.9",
        status="active"
    )
    assert event.source_file == "conditions.csv"
    assert event.description == "Type 2 Diabetes"
    print("test_clinical_event passed!")

if __name__ == "__main__":
    test_patient_demographics()
    test_clinical_event()
    print("All model tests passed!")
