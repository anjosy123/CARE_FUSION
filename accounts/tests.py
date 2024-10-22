from django.test import TestCase
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from django.contrib.auth.hashers import make_password
from accounts.models import Organizations
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
from datetime import datetime
from selenium.common.exceptions import TimeoutException
import time

class LoginTest(StaticLiveServerTestCase):
    test_results = []

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        cls.driver.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        cls.generate_pdf_report()
        super().tearDownClass()

    def setUp(self):
        # Create a verified organization user
        self.org = Organizations.objects.create(
            org_email='testorg@example.com',
            org_regid='ORG123',
            org_name='Test Organization',
            org_password=make_password('testpassword'),
            is_email_verified=True,
            approve=True
        )

    def test_organization_login(self):
        try:
            self.driver.get(f"{self.live_server_url}/login")
            
            email_field = self.driver.find_element(By.ID, "email")
            password_field = self.driver.find_element(By.ID, "passw1")
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")

            email_field.send_keys("testorg@example.com")
            password_field.send_keys("testpassword")
            login_button.click()

            # Wait for redirection
            WebDriverWait(self.driver, 10).until(
                EC.url_contains("palliatives_dashboard")
            )

            # Check if we're on the palliatives dashboard page
            self.assertIn("palliatives_dashboard", self.driver.current_url)

            # Wait for the dashboard content to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "dashboard-container"))
            )

            # Check for the welcome message
            welcome_selectors = [
                "//li[contains(@class, 'active')]//a[contains(text(), 'Welcome')]",
                "//li[contains(@class, 'active')]//a[contains(text(), 'testorg@example.com')]",
                "//li[contains(@class, 'active')]//a[contains(text(), 'Test Organization')]"
            ]

            welcome_element = None
            for selector in welcome_selectors:
                try:
                    welcome_element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    if welcome_element:
                        break
                except TimeoutException:
                    continue

            if not welcome_element:
                # Capture screenshot and page source for debugging
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                self.driver.save_screenshot(f"login_failure_{timestamp}.png")
                with open(f"page_source_{timestamp}.html", "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)
                self.fail("No welcome message found on the dashboard")

            self.assertTrue(welcome_element.is_displayed())

            # Check for other dashboard elements
            self.assertTrue(self.driver.find_element(By.CLASS_NAME, "dashboard-title").is_displayed())
            self.assertTrue(self.driver.find_element(By.ID, "recent-assignments").is_displayed())
            self.assertTrue(self.driver.find_element(By.ID, "pending-requests").is_displayed())
            self.assertTrue(self.driver.find_element(By.ID, "upcoming-team-visits").is_displayed())

            self.test_results.append(("Organization Login Test", "Passed"))

        except Exception as e:
            self.test_results.append(("Organization Login Test", f"Failed: {str(e)}"))
            raise

    @classmethod
    def generate_pdf_report(cls):
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"login_test_report_{timestamp}.pdf"
        filepath = os.path.join(desktop_path, filename)

        c = canvas.Canvas(filepath, pagesize=letter)
        width, height = letter

        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, "Login Test Report")
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 70, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        y = height - 100
        for test_name, result in cls.test_results:
            c.drawString(50, y, f"{test_name}: {result}")
            y -= 20

        c.save()
        print(f"Test report saved to: {filepath}")
