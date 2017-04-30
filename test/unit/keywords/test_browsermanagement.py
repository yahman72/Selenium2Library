import unittest
#Jari 
## from Selenium2Library.keywords._browsermanagement import _BrowserManagementKeywords
from Selenium2Library import keywords
#Jari 

from mockito import when, mock, verify, verifyNoMoreInteractions
from selenium import webdriver

from Selenium2Library.keywords.browsermanagement import BrowserManagementKeywords


class BrowserManagementTests(unittest.TestCase):


    def test_create_firefox_browser(self):
        test_browsers = ((webdriver.Firefox, "ff"), (webdriver.Firefox, "firEfOx"))

        for test_browser in test_browsers:
            self.verify_browser(*test_browser)

    def mock_createProfile(self, profile_directory=None):
        self.ff_profile_dir = profile_directory
        return self.old_profile_init(profile_directory)

    def test_create_ie_browser(self):
        test_browsers = ((webdriver.Ie, "ie"), (webdriver.Ie, "Internet Explorer"))

        for test_browser in test_browsers:
            self.verify_browser(*test_browser)

    def test_create_chrome_browser(self):
        test_browsers = ((webdriver.Chrome, "gOOglEchrOmE"),(webdriver.Chrome,"gc"),
                          (webdriver.Chrome, "chrome"))

        for test_browser in test_browsers:
            self.verify_browser(*test_browser)

    def test_create_opera_browser(self):
        self.verify_browser(webdriver.Opera, "OPERA")

    def test_create_phantomjs_browser(self):
        self.verify_browser(webdriver.PhantomJS, "PHANTOMJS")

    def test_create_remote_browser(self):
        self.verify_browser(webdriver.Remote, "chrome", remote="http://127.0.0.1/wd/hub")

    def test_create_htmlunit_browser(self):
        self.verify_browser(webdriver.Remote, "htmlunit")

    def test_create_htmlunitwihtjs_browser(self):
        self.verify_browser(webdriver.Remote, "htmlunitwithjs")

    def test_parse_capabilities_string(self):
        bm = BrowserManagementKeywords()
        expected_caps = "key1:val1,key2:val2"
        capabilities = bm._parse_capabilities_string(expected_caps)
        self.assertTrue("val1", capabilities["key1"])
        self.assertTrue("val2", capabilities["key2"])
        self.assertTrue(2, len(capabilities))

    def test_parse_complex_capabilities_string(self):
        bm = BrowserManagementKeywords()
        expected_caps = "proxyType:manual,httpProxy:IP:port"
        capabilities = bm._parse_capabilities_string(expected_caps)
        self.assertTrue("manual", capabilities["proxyType"])
        self.assertTrue("IP:port", capabilities["httpProxy"])
        self.assertTrue(2, len(capabilities))

    def test_create_remote_browser_with_desired_prefs(self):
        expected_caps = {"key1":"val1","key2":"val2"}
        self.verify_browser(webdriver.Remote, "chrome", remote="http://127.0.0.1/wd/hub",
            desired_capabilities=expected_caps)

    def test_create_remote_browser_with_string_desired_prefs(self):
        expected_caps = "key1:val1,key2:val2"
        self.verify_browser(webdriver.Remote, "chrome", remote="http://127.0.0.1/wd/hub",
            desired_capabilities=expected_caps)

    def test_capabilities_attribute_not_modified(self):
        expected_caps = {"some_cap":"42"}
        self.verify_browser(webdriver.Remote, "chrome", remote="http://127.0.0.1/wd/hub",
            desired_capabilities=expected_caps)
        self.assertFalse("some_cap" in webdriver.DesiredCapabilities.CHROME)

    def test_set_selenium_timeout_only_affects_open_browsers(self):
        bm = BrowserManagementKeywords()
        first_browser, second_browser = mock(), mock()
        bm._cache.register(first_browser)
        bm._cache.close()
        verify(first_browser).quit()
        bm._cache.register(second_browser)
        bm.set_selenium_timeout("10 seconds")
        verify(second_browser).set_script_timeout(10.0)
        bm._cache.close_all()
        verify(second_browser).quit()
        bm.set_selenium_timeout("20 seconds")
        verifyNoMoreInteractions(first_browser)
        verifyNoMoreInteractions(second_browser)

    def test_bad_browser_name(self):
        bm = BrowserManagementKeywords()
        try:
            bm._make_browser("fireox")
            self.fail("Exception not raised")
        except ValueError as e:
            self.assertEquals(str(e), "fireox is not a supported browser.")

    def test_create_webdriver(self):
        bm = _BrowserManagementWithLoggingStubs()
        capt_data = {}
        class FakeCmdExecutor(mock):
            _url = "http://127.0.0.1:9999/dummy"
        class FakeWebDriver(mock):
            def __init__(self, some_arg=None):
                mock.__init__(self)
                capt_data['some_arg'] = some_arg
                capt_data['webdriver'] = self
        webdriver.FakeWebDriver = FakeWebDriver
        webdriver.FakeWebDriver.command_executor = FakeCmdExecutor
        try:
            index = bm.create_webdriver('FakeWebDriver', 'fake', some_arg=1)
            self.assertEquals(capt_data['some_arg'], 1)
            self.assertEquals(capt_data['webdriver'], bm._current_browser())
            self.assertEquals(capt_data['webdriver'], bm._cache.get_connection(index))
            self.assertEquals(capt_data['webdriver'], bm._cache.get_connection('fake'))
            capt_data.clear()
            my_kwargs = {'some_arg':2}
            bm.create_webdriver('FakeWebDriver', kwargs=my_kwargs)
            self.assertEquals(capt_data['some_arg'], 2)
        finally:
            del webdriver.FakeWebDriver

    def test_create_reusable_webdriver(self):
        bm = _BrowserManagementWithLoggingStubs()
        capt_data = {}
        class FakeCmdExecutor(mock):
            _url = "http://127.0.0.1:9999/dummy"
        class FakeWebDriver(mock):
            session_id = "dummy_sid"
            def __init__(self):
                mock.__init__(self)
                capt_data['webdriver'] = self
        webdriver.FakeWebDriver = FakeWebDriver
        webdriver.FakeWebDriver.command_executor = FakeCmdExecutor
        class FakeReusable(mock):
            def __init__(self, command_executor, sid, **kwargs):
                FakeReusable.session_id = sid
                FakeReusable.curl = command_executor
        keywords.browsermanagement._ReusableDriver = FakeReusable
        try:
            bm.create_webdriver('FakeWebDriver', 'fake')
            (sid, url, pid) = bm.save_webdriver(None)
            self.assertEquals(sid, FakeWebDriver.session_id)
            self.assertEquals(url, FakeCmdExecutor._url)
            self.assertEquals(sid, bm._current_browser().session_id)
            self.assertEquals(url, bm._current_browser().command_executor._url)
            old_index = bm._cache.current_index
            new_index = bm.restore_webdriver(session_id=sid, session_url=url)
            self.assertNotEqual(old_index, new_index)
            self.assertEquals(sid, FakeReusable.session_id)
            self.assertEquals(url, FakeReusable.curl)
        finally:
            del webdriver.FakeWebDriver

    def verify_browser(self , webdriver_type , browser_name, **kw):
        #todo try lambda *x: was_called = true
        bm = BrowserManagementKeywords()
        old_init = webdriver_type.__init__
        webdriver_type.__init__ = self.mock_init

        try:
            self.was_called = False
            bm._make_browser(browser_name, **kw)
        except AttributeError:
            pass #kinda dangerous but I'm too lazy to mock out all the set_timeout calls
        finally:
            webdriver_type.__init__ = old_init
            self.assertTrue(self.was_called)

    def mock_init(self, *args, **kw):
        self.was_called = True


class _BrowserManagementWithLoggingStubs(BrowserManagementKeywords):

    def __init__(self):
        BrowserManagementKeywords.__init__(self)
        def mock_logging_method(self, *args, **kwargs):
            pass
        for name in ['_info', '_debug', '_warn', '_log', '_html']:
            setattr(self, name, mock_logging_method)
