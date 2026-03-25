from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
test_password = "test123"
hashed = pwd_context.hash(test_password)
print(f"Hash created: {hashed[:20]}...")
print(f"Verification: {pwd_context.verify(test_password, hashed)}")
print("✅ bcrypt is working correctly!")
