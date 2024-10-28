from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.contrib.auth.hashers import make_password
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from accounts.models import Staff, Organizations, User, PatientAssignment, ServiceRequest
import time
from datetime import datetime  # Keep this import for timestamps

class FunctionalityTests(StaticLiveServerTestCase):
    test_results = []

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        cls.driver.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        cls.print_test_results()  # New method to print results
        super().tearDownClass()

    def setUp(self):
        # Create test users and data
        # Create a doctor
        self.doctor = Staff.objects.create(
            username='testdoctor',
            email='doctor@test.com',
            password=make_password('doctorpass123'),
            role='DOCTOR',
            is_email_confirmed=True,
            must_change_password=False
        )

        # Create an organization
        self.org = Organizations.objects.create(
            org_email='testorg@example.com',
            org_regid='ORG123',
            org_name='Test Organization',
            org_password=make_password('orgpass123'),
            is_email_verified=True,
            approve=True
        )

        # Create an admin user
        self.admin = User.objects.create(
            username='admin',
            email='carefusion.ai@gmail.com',
            password=make_password('adminpass123'),
            is_email_verified=True,
            is_active=True
        )

        # Create a test patient and assignment for doctor
        self.patient = User.objects.create(
            username='testpatient',
            email='patient@test.com',
            password=make_password('patientpass123'),
            is_email_verified=True
        )

        self.assignment = PatientAssignment.objects.create(
            patient=self.patient,
            staff=self.doctor,
            organization=self.org,
            is_active=True
        )

        # Create a pending service request
        self.service_request = ServiceRequest.objects.create(
            patient=self.patient,
            organization=self.org,
            status='PENDING'
        )

        # Create a pending organization
        self.pending_org = Organizations.objects.create(
            org_email='pending@org.com',
            org_regid='PEND123',
            org_name='Pending Organization',
            org_password=make_password('pendingpass123'),
            is_email_verified=True,
            approve=False
        )

    def login_user(self, email, password):
        """Helper method to handle login"""
        try:
            # Update login URL to match your project's URL configuration
            login_url = f"{self.live_server_url}/accounts/login/"  # Added 'accounts/' prefix
            print(f"Attempting to access: {login_url}")
            
            self.driver.get(login_url)
            time.sleep(2)
            
            print(f"Current URL: {self.driver.current_url}")
            print(f"Page source: {self.driver.page_source}")
            
            # Wait for and fill email field
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
            email_field.clear()
            email_field.send_keys(email)
            
            # Wait for and fill password field
            password_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "pass1"))  # Updated to match your form
            )
            password_field.clear()
            password_field.send_keys(password)
            
            # Take screenshot before submitting
            self.driver.save_screenshot('before_login.png')
            
            # Find and click submit button using form ID
            form = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "loginForm"))
            )
            submit_button = form.find_element(By.CSS_SELECTOR, "button[type='submit']")
            submit_button.click()
            
            # Wait for redirect
            time.sleep(3)
            
            # Take screenshot after login attempt
            self.driver.save_screenshot('after_login.png')
            
            print(f"Login completed. Current URL: {self.driver.current_url}")
            
        except Exception as e:
            print(f"Login failed: {str(e)}")
            print("Current page source:", self.driver.page_source)
            self.driver.save_screenshot('login_error.png')
            raise

    def test_doctor_prescription_management(self):
        try:
            self.login_user("doctor@test.com", "doctorpass123")
            
            # Wait for doctor dashboard
            WebDriverWait(self.driver, 10).until(
                EC.url_contains("doctor_dashboard")
            )
            
            # Add more detailed logging
            current_url = self.driver.current_url
            print(f"After login redirect URL: {current_url}")
            
            self.test_results.append(("Doctor Login Test", "Passed"))
            
        except Exception as e:
            print(f"Test failed: {str(e)}")
            self.test_results.append(("Doctor Login Test", f"Failed: {str(e)}"))
            raise

    def test_organization_service_approval(self):
        try:
            # Login as organization
            self.driver.get(f"{self.live_server_url}/login")
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            self.driver.find_element(By.ID, "email").send_keys("testorg@example.com")
            self.driver.find_element(By.ID, "password").send_keys("orgpass123")
            self.driver.find_element(By.XPATH, "//button[@type='submit']").click()

            # Wait for organization dashboard
            WebDriverWait(self.driver, 10).until(
                EC.url_contains("palliatives_dashboard")
            )

            # Navigate to pending requests
            self.driver.get(f"{self.live_server_url}/service_requests")

            # Find and click approve button for the test service request
            approve_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, f"//button[@data-request-id='{self.service_request.id}']"))
            )
            approve_button.click()

            # Wait for success message
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "alert-success"))
            )

            # Verify request status changed
            self.service_request.refresh_from_db()
            self.assertEqual(self.service_request.status, 'APPROVED')

            self.test_results.append(("Organization Service Approval Test", "Passed"))

        except Exception as e:
            self.test_results.append(("Organization Service Approval Test", f"Failed: {str(e)}"))
            raise

    def test_admin_organization_approval(self):
        try:
            # Login as admin
            self.driver.get(f"{self.live_server_url}/login")
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "email"))
            )
            self.driver.find_element(By.ID, "email").send_keys("carefusion.ai@gmail.com")
            self.driver.find_element(By.ID, "password").send_keys("adminpass123")
            self.driver.find_element(By.XPATH, "//button[@type='submit']").click()

            # Wait for admin dashboard
            WebDriverWait(self.driver, 10).until(
                EC.url_contains("admin_dashboard")
            )

            # Navigate to organization approval page
            self.driver.get(f"{self.live_server_url}/approve_organizations")

            # Find and click approve button for pending organization
            approve_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, f"//button[@data-org-id='{self.pending_org.id}']"))
            )
            approve_button.click()

            # Wait for success message or page reload
            time.sleep(2)  # Allow time for the approval to process

            # Verify organization was approved
            self.pending_org.refresh_from_db()
            self.assertTrue(self.pending_org.approve)

            self.test_results.append(("Admin Organization Approval Test", "Passed"))

        except Exception as e:
            self.test_results.append(("Admin Organization Approval Test", f"Failed: {str(e)}"))
            raise

    @classmethod
    def print_test_results(cls):
        print("\nFunctionality Test Results:")
        print("=" * 30)
        for test_name, result in cls.test_results:
            print(f"{test_name}: {result}")
        print("=" * 30)
