import os.path
import os
import signal

import time
import types

from robot.errors import DataError
from robot.utils import secs_to_timestr, timestr_to_secs

from selenium import webdriver
from selenium.common.exceptions import NoSuchWindowException

from Selenium2Library.utils import BrowserCache
from Selenium2Library.locators import WindowManager
from Selenium2Library.keywords.logging import LoggingKeywords

from .keywordgroup import KeywordGroup

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FIREFOX_PROFILE_DIR = os.path.join(ROOT_DIR, 'resources', 'firefoxprofile')
BROWSER_NAMES = {'ff': "_make_ff",
                 'firefox': "_make_ff",
                 'ie': "_make_ie",
                 'internetexplorer': "_make_ie",
                 'googlechrome': "_make_chrome",
                 'gc': "_make_chrome",
                 'chrome': "_make_chrome",
                 'opera': "_make_opera",
                 'phantomjs': "_make_phantomjs",
                 'htmlunit': "_make_htmlunit",
                 'htmlunitwithjs': "_make_htmlunitwithjs",
                 'android': "_make_android",
                 'iphone': "_make_iphone",
                 'safari': "_make_safari",
                 'edge': "_make_edge"
                 }


class _ReusableDriver(webdriver.Remote, LoggingKeywords):
    def __init__(self, command_executor, sid, keep_alive=False, file_detector=None):

        self.reuse_session_id = sid
        super(_ReusableDriver, self).__init__(command_executor, desired_capabilities={},
                                              browser_profile=None,
                                              proxy=None, keep_alive=keep_alive,
                                              file_detector=file_detector)

    def stop_client(self):
        if self.pid is not None and self.pid != '':
            self._info("Stopping driver for session '%s' with PID: %s" % (self.session_id, self.pid))
            try:
                os.kill(int(self.pid), signal.SIGTERM)
            except EnvironmentError:
                self._warn("Failed to stop the driver with PID '%s' - please kill the process manually " % (self.pid))
        else:
            self._info("No driver process found for session '%s'" % (self.session_id))

    def start_session(self, desired_capabilities, browser_profile=None):
        self.session_id = self.reuse_session_id
        self._info("Reconnecting to session '%s' " % self.session_id)
        self.command_executor._commands["GetSessionData"] = ('GET', '/session/$sessionId')
        response = self.execute("GetSessionData")
        self._debug("Reconnect OK, session data: '%s' " % response)
        self.capabilities = response['value']
        self.w3c = "specificationLevel" in self.capabilities


class BrowserManagementKeywords(KeywordGroup):
    def __init__(self):
        self._cache = BrowserCache()
        self._window_manager = WindowManager()
        self._speed_in_secs = 0.0
        self._timeout_in_secs = float(5)
        self._implicit_wait_in_secs = float(0)

    # Public, open and close

    def close_all_browsers(self):
        """Closes all open browsers and resets the browser cache.

        After this keyword new indexes returned from `Open Browser` keyword
        are reset to 1.

        This keyword should be used in test or suite teardown to make sure
        all browsers are closed.
        """
        self._debug('Closing all browsers')
        self._cache.close_all()

    def close_browser(self):
        """Closes the current browser."""
        if self._cache.current:
            self._debug('Closing browser with session id %s'
                        % self._cache.current.session_id)
            self._cache.close()

    def open_browser(self, url, browser='firefox', alias=None, remote_url=False,
                     desired_capabilities=None, ff_profile_dir=None):
        """Opens a new browser instance to given URL.

        Returns the index of this browser instance which can be used later to
        switch back to it. Index starts from 1 and is reset back to it when
        `Close All Browsers` keyword is used. See `Switch Browser` for
        example.

        Optional alias is an alias for the browser instance and it can be used
        for switching between browsers (just as index can be used). See `Switch
        Browser` for more details.

        Possible values for `browser` are as follows:

        | firefox          | FireFox   |
        | ff               | FireFox   |
        | internetexplorer | Internet Explorer |
        | ie               | Internet Explorer |
        | googlechrome     | Google Chrome |
        | gc               | Google Chrome |
        | chrome           | Google Chrome |
        | opera            | Opera         |
        | phantomjs        | PhantomJS     |
        | htmlunit         | HTMLUnit      |
        | htmlunitwithjs   | HTMLUnit with Javascipt support |
        | android          | Android       |
        | iphone           | Iphone        |
        | safari           | Safari        |
        | edge             | Edge          |


        Note, that you will encounter strange behavior, if you open
        multiple Internet Explorer browser instances. That is also why
        `Switch Browser` only works with one IE browser at most.
        For more information see:
        http://selenium-grid.seleniumhq.org/faq.html#i_get_some_strange_errors_when_i_run_multiple_internet_explorer_instances_on_the_same_machine

        Optional 'remote_url' is the url for a remote selenium server for example
        http://127.0.0.1:4444/wd/hub. If you specify a value for remote you can
        also specify 'desired_capabilities' which is a string in the form
        key1:val1,key2:val2 that will be used to specify desired_capabilities
        to the remote server. This is useful for doing things like specify a
        proxy server for internet explorer or for specify browser and os if your
        using saucelabs.com. 'desired_capabilities' can also be a dictonary
        (created with 'Create Dictionary') to allow for more complex configurations.

        Optional 'ff_profile_dir' is the path to the firefox profile dir if you
        wish to overwrite the default.
        """
        if remote_url:
            self._info("Opening browser '%s' to base url '%s' through remote server at '%s'"
                       % (browser, url, remote_url))
        else:
            self._info("Opening browser '%s' to base url '%s'" % (browser, url))
        browser_name = browser
        browser = self._make_browser(browser_name, desired_capabilities, ff_profile_dir, remote_url)
        try:
            browser.get(url)
        except:
            self._cache.register(browser, alias)
            self._debug("Opened browser with session id %s but failed to open url '%s'"
                        % (browser.session_id, url))
            raise
        self._debug('Opened browser with session id %s'
                    % browser.session_id)
        return self._cache.register(browser, alias)

    def create_webdriver(self, driver_name, alias=None, kwargs={}, **init_kwargs):
        """Creates an instance of a WebDriver.

        Like `Open Browser`, but allows passing arguments to a WebDriver's
        __init__. _Open Browser_ is preferred over _Create Webdriver_ when
        feasible.

        Returns the index of this browser instance which can be used later to
        switch back to it. Index starts from 1 and is reset back to it when
        `Close All Browsers` keyword is used. See `Switch Browser` for
        example.

        `driver_name` must be the exact name of a WebDriver in
        _selenium.webdriver_ to use. WebDriver names include: Firefox, Chrome,
        Ie, Opera, Safari, PhantomJS, and Remote.

        Use keyword arguments to specify the arguments you want to pass to
        the WebDriver's __init__. The values of the arguments are not
        processed in any way before being passed on. For Robot Framework
        < 2.8, which does not support keyword arguments, create a keyword
        dictionary and pass it in as argument `kwargs`. See the
        [http://selenium.googlecode.com/git/docs/api/py/api.html|Selenium API Documentation]
        for information about argument names and appropriate argument values.

        Examples:
        | # use proxy for Firefox     |              |                                           |                         |
        | ${proxy}=                   | Evaluate     | sys.modules['selenium.webdriver'].Proxy() | sys, selenium.webdriver |
        | ${proxy.http_proxy}=        | Set Variable | localhost:8888                            |                         |
        | Create Webdriver            | Firefox      | proxy=${proxy}                            |                         |
        | # use a proxy for PhantomJS |              |                                           |                         |
        | ${service args}=            | Create List  | --proxy=192.168.132.104:8888              |                         |
        | Create Webdriver            | PhantomJS    | service_args=${service args}              |                         |

        Example for Robot Framework < 2.8:
        | # debug IE driver |                   |                  |                                |
        | ${kwargs}=        | Create Dictionary | log_level=DEBUG  | log_file=%{HOMEPATH}${/}ie.log |
        | Create Webdriver  | Ie                | kwargs=${kwargs} |                                |
        """
        if not isinstance(kwargs, dict):
            raise RuntimeError("kwargs must be a dictionary.")
        for arg_name in kwargs:
            if arg_name in init_kwargs:
                raise RuntimeError("Got multiple values for argument '%s'." % arg_name)
            init_kwargs[arg_name] = kwargs[arg_name]
        driver_name = driver_name.strip()
        try:
            creation_func = getattr(webdriver, driver_name)
        except AttributeError:
            raise RuntimeError("'%s' is not a valid WebDriver name" % driver_name)
        self._info("Creating an instance of the %s WebDriver" % driver_name)
        driver = creation_func(**init_kwargs)
        self._debug("Created %s WebDriver instance with session id %s" % (driver_name, driver.session_id))
        return self._cache.register(driver, alias)

    def save_webdriver(self, file=''):
        """Stores the current web-driver session.

        NOTE: This KW is not for production use. The `Save Webdriver` and `Restore Webdriver` KW's are there to
        speed up the test case development i.e. instead of always opening new browser window you can reconnect to
        an already opened Browser window.

        This KW makes the WebDriver sessions persistent. I.e. you can store the session(s) and leave the browser
        window(s) open after a pybot (test suite) execution. On the next pybot execution you can reconnect to those
        already opened browser windows and avoid that slow opening of new browser window(s) step and possibly other
        steps (e.g. login) that you might do in your suite/test set-up phase.
        NOTE: When re-connecting the session must exists on the server side, in some scenarios the session
        might have timed out and the re-connect will fail.

        Saves the session information into file or returns it.

        The file name is taken from the _file_ argument.
        This accepts plain file name (e.g. "mysession.txt") and path-to-file (e.g. "/tmp/mysession.txt") format.
        The _file_ argument has following special values:
        - empty string i.e. ``${EMPTY}`` (default): the session is stored in the current execution directory in a 
          file called "session_<alias>.tmp" (if the connection has an alias) or "session_<index>.tmp" 
          (if the connection does not have an alias).
        - None i.e. ``${None}``: no file is created. Returns a tuplet where the 1st value is the session ID and the 2nd
          value is the Webdriver URL.

        Returns the session file-name, unless _file_ argument is None (see above).

        Examples:
        | Create Webdriver | Firefox         |                |              |                              |
        | ${file} =        | Save Webdriver  |                |              | # saved to "session_1.tmp"   |
        | Create Webdriver | Firefox         | alias=foo      |              |                              |
        | ${file} =        | Save Webdriver  |                |              | # saved to "session_foo.tmp" |
        | ${file} =        | Save Webdriver  | file=dummy.tmp |              | # saved to "dummy.tmp"       |
        | ${sid}           | ${url} =        | Save Webdriver | file=${None} | # no file created            |

        See also `Restore Webdriver`
        """
        self._info("Saving WebDriver session data")
        driver_service_attr_names = ['service', 'iedriver']
        cb = self._current_browser()
        sid = cb.session_id
        curl = cb.command_executor._url
        # get pid if we are in a restored this session 
        pid = cb.__dict__.get("pid", None)
        if pid is None:
            # get driver executable PID
            # this part is browser-dependant, currently tested only with: FF, GC & IE
            self._debug("'%s'" % self._current_browser().__dict__)
            for srvc_name in driver_service_attr_names:
                srvc = cb.__dict__.get(srvc_name, None)
                if srvc is not None:
                    pid = srvc.process.pid
                    break
            if pid is None:
                self._info(
                    "Could not find driver process - we will not attempt to " +
                    " kill the driver process after re-connecting to it with restore_session() ")
        if file is None:
            return (sid, curl, pid)
        elif file == "":
            inv_dict = {v: k for k, v in self._cache._aliases.items()}
            session_name = inv_dict.get(self._cache.current_index, self._cache.current_index)
            file = "session_%s.tmp" % (session_name)
        self._debug("Storing session (%s-%s) in file '%s'" % (sid, curl, file))
        session_file = open(file, 'w+')
        session_file.write("%s\n" % sid)
        session_file.write("%s\n" % curl)
        if pid is not None:
            session_file.write("%s\n" % pid)
        session_file.close()
        return file

    def restore_webdriver(self, alias=None, file=None, session_id=None, session_url=None, session_pid=None,
                          delete_file=True):
        """Connects to an already opened web-driver session.

        NOTE: This KW is not for production use. The `Save Webdriver` and `Restore Webdriver` KW's are there to
        speed up the test case development i.e. instead of always opening new browser window you can reconnect to
        an already opened Browser window.

        Restores a Webdriver Session that has been saved using the `Save Webdriver` KW.

        Optional _alias_ is an alias for the browser instance and it can be used
        for switching between browsers (just as index can be used). See `Switch
        Browser` for more details.

        The session can be restored by:
        - using the default session file (e.g. with `alias=foo` we try to read the session info from a file called
          "session_foo.tmp")
        - using explicit file: file-name is passed in _file_ argument. See `Save Webdriver` KW for _file_
          argument documentation
        - using the _session_id_ and _session_url_ arguments

        Optional _delete_file_ can be used to delete (default) the file after the session has been restored.

        Returns the index of this browser instance which can be used later to
        switch back to it. Index starts from 1 and is reset back to it when
        `Close All Browsers` keyword is used. See `Switch Browser` for
        example.

        Examples:
        | Restore Webdriver | alias=foo    |              | #read from "session_foo.tmp" and register with alias "foo" |
        | Restore Webdriver | alias=bar    | file=foo.tmp | #read from "foo.tmp" and register with alias "bar"         |
        | Restore Webdriver |              | file=foo.tmp | #read from "foo.tmp" and register without alias            |
        | #do not use file and register without alias | |    |                                                         |
        | Restore Webdriver | session_id=x | session_url=http://127.0.0.1:9999/hub |                                   |
        """
        self._info("Restoring WebDriver session")
        if session_id is not None or session_url is not None:
            if session_id is None and session_url is None:
                raise RuntimeError("both session_id and session_url cannot be None.")
            saved_sid = session_id
            saved_curl = session_url
        else:
            if file is None:
                if alias is None:
                    raise RuntimeError("both alias and file cannot be None.")
                else:
                    file = "session_%s.tmp" % (alias)
            session_file = open(file, 'r+')
            saved_sid = session_file.readline().replace("\n", "").replace("\r", "")
            saved_curl = session_file.readline().replace("\n", "").replace("\r", "")
            session_pid = session_file.readline().replace("\n", "").replace("\r", "")
            session_file.close()
        self._debug("Reconnecting to '%s' with session id '%s' - alias: '%s' " % (saved_curl, saved_sid, alias))
        try:
            driver = _ReusableDriver(saved_curl, saved_sid)
            driver.pid = session_pid
        except:
            raise
        finally:
            if delete_file and session_id is None and session_url is None:
                os.remove(file)
        return self._cache.register(driver, alias)

    def switch_browser(self, index_or_alias):
        """Switches between active browsers using index or alias.

        Index is returned from `Open Browser` and alias can be given to it.

        Example:
        | Open Browser        | http://google.com | ff       |
        | Location Should Be  | http://google.com |          |
        | Open Browser        | http://yahoo.com  | ie       | 2nd conn |
        | Location Should Be  | http://yahoo.com  |          |
        | Switch Browser      | 1                 | # index  |
        | Page Should Contain | I'm feeling lucky |          |
        | Switch Browser      | 2nd conn          | # alias  |
        | Page Should Contain | More Yahoo!       |          |
        | Close All Browsers  |                   |          |

        Above example expects that there was no other open browsers when
        opening the first one because it used index '1' when switching to it
        later. If you aren't sure about that you can store the index into
        a variable as below.

        | ${id} =            | Open Browser  | http://google.com | *firefox |
        | # Do something ... |
        | Switch Browser     | ${id}         |                   |          |
        """
        try:
            self._cache.switch(index_or_alias)
            self._debug('Switched to browser with Selenium session id %s'
                        % self._cache.current.session_id)
        except (RuntimeError, DataError):  # RF 2.6 uses RE, earlier DE
            raise RuntimeError("No browser with index or alias '%s' found."
                               % index_or_alias)

    # Public, window management

    def close_window(self):
        """Closes currently opened pop-up window."""
        self._current_browser().close()

    def get_window_identifiers(self):
        """Returns and logs id attributes of all windows known to the browser."""
        return self._log_list(self._window_manager.get_window_ids(self._current_browser()))

    def get_window_names(self):
        """Returns and logs names of all windows known to the browser."""
        values = self._window_manager.get_window_names(self._current_browser())

        # for backward compatibility, since Selenium 1 would always
        # return this constant value for the main window
        if len(values) and values[0] == 'undefined':
            values[0] = 'selenium_main_app_window'

        return self._log_list(values)

    def get_window_titles(self):
        """Returns and logs titles of all windows known to the browser."""
        return self._log_list(self._window_manager.get_window_titles(self._current_browser()))

    def maximize_browser_window(self):
        """Maximizes current browser window."""
        self._current_browser().maximize_window()

    def get_window_size(self):
        """Returns current window size as `width` then `height`.

        Example:
        | ${width} | ${height}= | Get Window Size |
        """
        size = self._current_browser().get_window_size()
        return size['width'], size['height']

    def set_window_size(self, width, height):
        """Sets the `width` and `height` of the current window to the specified values.

        Example:
        | Set Window Size | ${800} | ${600}       |
        | ${width} | ${height}= | Get Window Size |
        | Should Be Equal | ${width}  | ${800}    |
        | Should Be Equal | ${height} | ${600}    |
        """
        return self._current_browser().set_window_size(width, height)

    def get_window_position(self):
        """Returns current window position as `x` then `y` (relative to the left and top of the screen).

        Example:
        | ${x} | ${y}= | Get Window Position |
        """
        position = self._current_browser().get_window_position()
        return position['x'], position['y']

    def set_window_position(self, x, y):
        """Sets the position x and y of the current window (relative to the left and top of the screen) to the specified values.

        Example:
        | Set Window Position | ${8}    | ${10}               |
        | ${x}                | ${y}=   | Get Window Position |
        | Should Be Equal     | ${x}    | ${8}                |
        | Should Be Equal     | ${y}    | ${10}               |
        """
        return self._current_browser().set_window_position(x, y)

    def select_frame(self, locator):
        """Sets frame identified by `locator` as current frame.

        Key attributes for frames are `id` and `name.` See `introduction` for
        details about locating elements.
        """
        self._info("Selecting frame '%s'." % locator)
        element = self._element_find(locator, True, True)
        self._current_browser().switch_to_frame(element)

    def select_window(self, locator=None):
        """Selects the window matching locator and return previous window handle.

        locator: any of name, title, url, window handle, excluded handle's list, or special words.
        return: either current window handle before selecting, or None if no current window.

        If the window is found, all subsequent commands use that window, until
        this keyword is used again. If the window is not found, this keyword fails.

        By default, when a locator value is provided,
        it is matched against the title of the window and the
        javascript name of the window. If multiple windows with
        same identifier are found, the first one is selected.

        There are some special locators for searching target window:
        string 'main' (default): select the main window;
        string 'self': only return current window handle;
        string 'new': select the last-indexed window assuming it is the newest opened window
        window list: select the first window not in given list (See 'List Windows' to get the list)

        It is also possible to specify the approach Selenium2Library should take
        to find a window by specifying a locator strategy:

        | *Strategy* | *Example*                               | *Description*                        |
        | title      | Select Window `|` title=My Document     | Matches by window title              |
        | name       | Select Window `|` name=${name}          | Matches by window javascript name    |
        | url        | Select Window `|` url=http://google.com | Matches by window's current URL      |

        Example:
        | Click Link | popup_link | # opens new window |
        | Select Window | popupName |
        | Title Should Be | Popup Title |
        | Select Window |  | | # Chooses the main window again |
        """
        try:
            return self._current_browser().current_window_handle
        except NoSuchWindowException:
            pass
        finally:
            self._window_manager.select(self._current_browser(), locator)

    def list_windows(self):
        """Return all current window handles as a list"""
        return self._current_browser().window_handles

    def unselect_frame(self):
        """Sets the top frame as the current frame."""
        self._current_browser().switch_to_default_content()

    # Public, browser/current page properties

    def get_location(self):
        """Returns the current location."""
        return self._current_browser().current_url

    def get_locations(self):
        """Returns and logs current locations of all windows known to the browser."""
        return self._log_list(
            [window_info[4] for window_info in
             self._window_manager._get_window_infos(self._current_browser())]
        )

    def get_source(self):
        """Returns the entire html source of the current page or frame."""
        return self._current_browser().page_source

    def get_title(self):
        """Returns title of current page."""
        return self._current_browser().title

    def location_should_be(self, url):
        """Verifies that current URL is exactly `url`."""
        actual = self.get_location()
        if actual != url:
            raise AssertionError("Location should have been '%s' but was '%s'"
                                 % (url, actual))
        self._info("Current location is '%s'." % url)

    def location_should_contain(self, expected):
        """Verifies that current URL contains `expected`."""
        actual = self.get_location()
        if not expected in actual:
            raise AssertionError("Location should have contained '%s' "
                                 "but it was '%s'." % (expected, actual))
        self._info("Current location contains '%s'." % expected)

    def log_location(self):
        """Logs and returns the current location."""
        url = self.get_location()
        self._info(url)
        return url

    def log_source(self, loglevel='INFO'):
        """Logs and returns the entire html source of the current page or frame.

        The `loglevel` argument defines the used log level. Valid log levels are
        WARN, INFO (default), DEBUG, and NONE (no logging).
        """
        source = self.get_source()
        self._log(source, loglevel.upper())
        return source

    def log_title(self):
        """Logs and returns the title of current page."""
        title = self.get_title()
        self._info(title)
        return title

    def title_should_be(self, title):
        """Verifies that current page title equals `title`."""
        actual = self.get_title()
        if actual != title:
            raise AssertionError("Title should have been '%s' but was '%s'"
                                 % (title, actual))
        self._info("Page title is '%s'." % title)

    # Public, navigation

    def go_back(self):
        """Simulates the user clicking the "back" button on their browser."""
        self._current_browser().back()

    def go_to(self, url):
        """Navigates the active browser instance to the provided URL."""
        self._info("Opening url '%s'" % url)
        self._current_browser().get(url)

    def reload_page(self):
        """Simulates user reloading page."""
        self._current_browser().refresh()

    # Public, execution properties

    def get_selenium_speed(self):
        """Gets the delay in seconds that is waited after each Selenium command.

        See `Set Selenium Speed` for an explanation."""
        return secs_to_timestr(self._speed_in_secs)

    def get_selenium_timeout(self):
        """Gets the timeout in seconds that is used by various keywords.

        See `Set Selenium Timeout` for an explanation."""
        return secs_to_timestr(self._timeout_in_secs)

    def get_selenium_implicit_wait(self):
        """Gets the wait in seconds that is waited by Selenium.

        See `Set Selenium Implicit Wait` for an explanation."""
        return secs_to_timestr(self._implicit_wait_in_secs)

    def set_selenium_speed(self, seconds):
        """Sets the delay in seconds that is waited after each Selenium command.

        This is useful mainly in slowing down the test execution to be able to
        view the execution. `seconds` may be given in Robot Framework time
        format. Returns the previous speed value in seconds.

        One keyword may execute one or many Selenium commands and therefore
        one keyword may slow down more than the ``seconds`` argument defines.
        Example if delay is set to 1 second and because `Click Element`
        executes two Selenium commands, then the total delay will be 2 seconds.
        But because `Page Should Contain Element` executes only one selenium
        command, then the total delay will be 1 second.

        Example:
        | Set Selenium Speed | .5 seconds |
        """
        old_speed = self._speed_in_secs
        self._speed_in_secs = timestr_to_secs(seconds)
        for browser in self._cache.browsers:
            browser._speed = self._speed_in_secs
            self._monkey_patch_speed(browser)
        return old_speed

    def set_selenium_timeout(self, seconds):
        """Sets the timeout in seconds used by various keywords.

        There are several `Wait ...` keywords that take timeout as an
        argument. All of these timeout arguments are optional. The timeout
        used by all of them can be set globally using this keyword.
        See `Timeouts` for more information about timeouts.

        The previous timeout value is returned by this keyword and can
        be used to set the old value back later. The default timeout
        is 5 seconds, but it can be altered in `importing`.

        Example:
        | ${orig timeout} = | Set Selenium Timeout | 15 seconds |
        | Open page that loads slowly |
        | Set Selenium Timeout | ${orig timeout} |
        """
        old_timeout = self.get_selenium_timeout()
        self._timeout_in_secs = timestr_to_secs(seconds)
        for browser in self._cache.get_open_browsers():
            browser.set_script_timeout(self._timeout_in_secs)
        return old_timeout

    def set_selenium_implicit_wait(self, seconds):
        """Sets Selenium 2's default implicit wait in seconds and
        sets the implicit wait for all open browsers.

        From selenium 2 function 'Sets a sticky timeout to implicitly
            wait for an element to be found, or a command to complete.
            This method only needs to be called one time per session.'

        Example:
        | ${orig wait} = | Set Selenium Implicit Wait | 10 seconds |
        | Perform AJAX call that is slow |
        | Set Selenium Implicit Wait | ${orig wait} |
        """
        old_wait = self.get_selenium_implicit_wait()
        self._implicit_wait_in_secs = timestr_to_secs(seconds)
        for browser in self._cache.get_open_browsers():
            browser.implicitly_wait(self._implicit_wait_in_secs)
        return old_wait

    def set_browser_implicit_wait(self, seconds):
        """Sets current browser's implicit wait in seconds.

        From selenium 2 function 'Sets a sticky timeout to implicitly
            wait for an element to be found, or a command to complete.
            This method only needs to be called one time per session.'

        Example:
        | Set Browser Implicit Wait | 10 seconds |

        See also `Set Selenium Implicit Wait`.
        """
        implicit_wait_in_secs = timestr_to_secs(seconds)
        self._current_browser().implicitly_wait(implicit_wait_in_secs)

    # Private

    def _current_browser(self):
        if not self._cache.current:
            raise RuntimeError('No browser is open')
        return self._cache.current

    def _get_browser_creation_function(self, browser_name):
        func_name = BROWSER_NAMES.get(browser_name.lower().replace(' ', ''))
        return getattr(self, func_name) if func_name else None

    def _make_browser(self, browser_name, desired_capabilities=None,
                      profile_dir=None, remote=None):
        creation_func = self._get_browser_creation_function(browser_name)

        if not creation_func:
            raise ValueError(browser_name + " is not a supported browser.")

        browser = creation_func(remote, desired_capabilities, profile_dir)
        browser.set_script_timeout(self._timeout_in_secs)
        browser.implicitly_wait(self._implicit_wait_in_secs)

        return browser

    def _make_ff(self, remote, desired_capabilites, profile_dir):

        if not profile_dir: profile_dir = FIREFOX_PROFILE_DIR
        profile = webdriver.FirefoxProfile(profile_dir)
        if remote:
            browser = self._create_remote_web_driver(webdriver.DesiredCapabilities.FIREFOX,
                                                     remote, desired_capabilites, profile)
        else:
            browser = webdriver.Firefox(firefox_profile=profile)
        return browser

    def _make_ie(self, remote, desired_capabilities, profile_dir):
        return self._generic_make_browser(webdriver.Ie,
                                          webdriver.DesiredCapabilities.INTERNETEXPLORER, remote, desired_capabilities)

    def _make_chrome(self, remote, desired_capabilities, profile_dir):
        return self._generic_make_browser(webdriver.Chrome,
                                          webdriver.DesiredCapabilities.CHROME, remote, desired_capabilities)

    def _make_opera(self, remote, desired_capabilities, profile_dir):
        return self._generic_make_browser(webdriver.Opera,
                                          webdriver.DesiredCapabilities.OPERA, remote, desired_capabilities)

    def _make_phantomjs(self, remote, desired_capabilities, profile_dir):
        return self._generic_make_browser(webdriver.PhantomJS,
                                          webdriver.DesiredCapabilities.PHANTOMJS, remote, desired_capabilities)

    def _make_htmlunit(self, remote, desired_capabilities, profile_dir):
        return self._generic_make_browser(webdriver.Remote,
                                          webdriver.DesiredCapabilities.HTMLUNIT, remote, desired_capabilities)

    def _make_htmlunitwithjs(self, remote, desired_capabilities, profile_dir):
        return self._generic_make_browser(webdriver.Remote,
                                          webdriver.DesiredCapabilities.HTMLUNITWITHJS, remote, desired_capabilities)

    def _make_android(self, remote, desired_capabilities, profile_dir):
        return self._generic_make_browser(webdriver.Remote,
                                          webdriver.DesiredCapabilities.ANDROID, remote, desired_capabilities)

    def _make_iphone(self, remote, desired_capabilities, profile_dir):
        return self._generic_make_browser(webdriver.Remote,
                                          webdriver.DesiredCapabilities.IPHONE, remote, desired_capabilities)

    def _make_safari(self, remote, desired_capabilities, profile_dir):
        return self._generic_make_browser(webdriver.Safari,
                                          webdriver.DesiredCapabilities.SAFARI, remote, desired_capabilities)

    def _make_edge(self, remote, desired_capabilities, profile_dir):
        if hasattr(webdriver, 'Edge'):
            return self._generic_make_browser(webdriver.Edge,
                                              webdriver.DesiredCapabilities.EDGE, remote, desired_capabilities)
        else:
            raise ValueError(
                "Edge is not a supported browser with your version of Selenium python library. Please, upgrade to minimum required version 2.47.0.")

    def _generic_make_browser(self, webdriver_type, desired_cap_type, remote_url, desired_caps):
        '''most of the make browser functions just call this function which creates the
        appropriate web-driver'''
        if not remote_url:
            browser = webdriver_type()
        else:
            browser = self._create_remote_web_driver(desired_cap_type, remote_url, desired_caps)
        return browser

    def _create_remote_web_driver(self, capabilities_type, remote_url, desired_capabilities=None, profile=None):
        '''parses the string based desired_capabilities if neccessary and
        creates the associated remote web driver'''

        desired_capabilities_object = capabilities_type.copy()

        if type(desired_capabilities) in (str, unicode):
            desired_capabilities = self._parse_capabilities_string(desired_capabilities)

        desired_capabilities_object.update(desired_capabilities or {})

        return webdriver.Remote(desired_capabilities=desired_capabilities_object,
                                command_executor=str(remote_url), browser_profile=profile)

    def _parse_capabilities_string(self, capabilities_string):
        '''parses the string based desired_capabilities which should be in the form
        key1:val1,key2:val2
        '''
        desired_capabilities = {}

        if not capabilities_string:
            return desired_capabilities

        for cap in capabilities_string.split(","):
            (key, value) = cap.split(":", 1)
            desired_capabilities[key.strip()] = value.strip()

        return desired_capabilities

    def _get_speed(self, browser):
        return browser._speed if hasattr(browser, '_speed') else 0.0

    def _monkey_patch_speed(self, browser):
        def execute(self, driver_command, params=None):
            result = self._base_execute(driver_command, params)
            speed = self._speed if hasattr(self, '_speed') else 0.0
            if speed > 0:
                time.sleep(speed)
            return result

        if not hasattr(browser, '_base_execute'):
            browser._base_execute = browser.execute
            browser.execute = types.MethodType(execute, browser)
