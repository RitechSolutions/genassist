from injector import Injector
from app.dependencies.dependency_injection import Dependencies

def create_injector() -> Injector:
    return Injector([Dependencies()])

injector: Injector = create_injector()
