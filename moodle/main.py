#! /usr/bin/env python
import cmd
import sys
from argparse import ArgumentParser
import json
import logging
import re
import os
import sys
try:
    import urllib3
except ImportError:
    urllib3 = None
import getpass
import requests
from bs4 import BeautifulSoup


# python 2 and 3 compatible input
cinput = input if sys.version_info[0] == 3 else raw_input

# avoid annoying warnings from SSL
if urllib3 is not None:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger()


class InvalidPassword(Exception):
    pass


class Parser:
    def __init__(self, html_doc):
        self.soup = BeautifulSoup(html_doc, 'html.parser')
        self.find = self.soup.find

    def course_list(self):
        for item in self.soup.find_all("a", {"class": "list-group-item-action"}):
            datakey = item.get("data-key", "")
            if not datakey.isdigit():
                continue
            href = item['href']
            if '#' in href:
                continue
            title = " ".join(x.capitalize() for x in item.text.strip().split()[1:])
            yield title, href

    def module_list(self):
        for item in self.soup.find_all("h3", {"class": "sectionname"}):
            if 'accesshide' in item['class']:
                continue
            yield item.text.strip(), item.find('a')['href']


class Moodle:
    def __init__(self, session, url):
        self.session = session
        self.url = url

    def download(self, url):
        if url.startswith('/'):
            url = self.url + url
        r = self.session.get(url, verify=False, timeout=10)
        return Parser(r.content)
   
    def download_link(self, url, title, path):
        logger.debug("Downloading '%s'" % title)
        if not title:
            logger.warning("Trying to download an empty title. skipping url %s" % url)
            return
        r = self.session.get(url, verify=False)
        cd = r.headers.get("Content-Disposition", '')
        m = re.match('.*filename="(.*?)".*', cd)
        filename = m.group(1) if m else title
        logger.info("Downloading file %s" % filename)
        with open(os.path.join(path, filename.replace('/', '_')), 'bw+') as fd:
            if not r.url.startswith(self.url):
                fd.write(bytearray('link: %s\n' % r.url, 'utf-8'))
            else:
                fd.write(r.content)
        logger.info("File %s downloaded" % filename)
   
    def get_subjects(self):
        p = self.download("/my/")
        for title, href in (p.course_list()):
            yield title, href
        
    def get_subject_content(self, id, subject_href):
        parser = self.download(subject_href)
        if id is None:
            id = 'region-main'
        content = parser.find(id=id)
        if not content:
            logger.info("Subject without content: %s" % id)
            return
        for link in content.find_all('a'):
            href = link.get('href', '')
            for i in link.find_all(attrs={'class': 'accesshide'}):
                i.clear()
            title = link.text.strip()
            if '#' in href:
                logging.info("Ignoring link to %s" % title)
                continue
            yield title, href

    def get_assign_content(self, href):
        parser = self.download(href)
        content = parser.find(id='region-main')
        for link in content.find_all('a'):
            href = link.get('href', '')
            for i in link.find_all(attrs={'class': 'accesshide'}):
                i.clear()
            title = link.text.strip()
            if '#' in href:
                logging.info("Ignoring link to %s" % title)
                continue
            yield title, href
        

class MoodleShell(cmd.Cmd):
    intro = """
Now you are logged in.
Next steps:
- Run "select" to select a subject. It allows completion.
- Then run "download" to download a module. No arguments to download them all.
    """

    def __init__(self, moodle, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subject = None
        self.moodle = moodle

    def download_subject(self, id, path):
        logger.info("download_subject %s %s" % (id, path))
        logger.debug("Selecting section with id = %s" % id)
        if not os.path.exists(path):
            os.makedirs(path)
        for title, href in self.moodle.get_subject_content(id, self.subject['href']):
            if 'mod/assign/view.php?id=' in href:
                assignpath = os.path.join(path, title.replace(' ', '_'))
                os.makedirs(assignpath)
                for title2, href2 in self.moodle.get_assign_content(href):
                    self.moodle.download_link(href2, title2, assignpath)
            else:
                self.moodle.download_link(href, title, path)

    def do_select(self, arg):
        print("selected: ", arg)
        self.subject = dict(
                title=arg,
                href=self.choices[arg],
        )
        self.prompt = "%s$ " % arg

    def complete_select(self, text, line, begidx, endidx):
        try:
            self.choices = {}
            result = []
            for title, href in self.moodle.get_subjects():
                _title = title.replace(" ", "_")
                if text and not text.lower() in _title.lower():
                    continue
                result.append(_title)
                self.choices[_title] = href
            return result
        except Exception as e:
            print(e)

    def help_select(self):
        print("Select a subject")

    def do_download(self, arg):
        logger.debug("do_download %s %s" % (arg, self.choices))
        path = input("Output path? ")
        if not arg or arg == '_EVERYTHING_':
            #this is just a patch to ensure choices has the last data
            self.complete_download(None, None, None, None)
            for title, id in self.choices.items():
                self.download_subject(id, os.path.join(path, title[:20]))
        else:
            id = self.choices[arg]
            self.download_subject(id, path)

    def complete_download(self, text, line, begidx, endidx):
        if self.subject is None:
            print("you must select a subject")
            return

        try:
            self.choices = {}
            p = self.moodle.download(self.subject['href'])
            
            result = []
            if not text or text.upper() in '_EVERYTHING_':
                result.append('_EVERYTHING_')
            for title, href in (p.module_list()):
                _title = title.replace(" ", "_")
                url, _, id = href.partition('#')
                self.choices[_title] = id
                if text and text.lower() not in _title.lower():
                    continue
                result.append(_title)
            return result
        except Exception as e:
            print(e)

    def help_download(self):
        print("Downloads a module or subject")

    def do_EOF(self, arg):
        return True

    def help_EOF(self):
        print("Exit program. Shortcut: CTRL+D")


def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    # taken from https://www.peterbe.com/plog/best-practice-with-retries-with-requests
    session = session or requests.Session()
    retry = requests.packages.urllib3.util.retry.Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def getsession(url, user, password):
    s = requests.Session()
    #return s
    r = s.get(url, verify=False)
    data = dict(
        adAS_i18n_theme='es',
        adAS_mode='authn',
        adAS_password=password,
        adAS_username=user,
    )
    try:
        r = s.post(r.url, data=data, verify=False, timeout=4)
    except requests.exceptions.ReadTimeout:
        raise InvalidPassword()
    bs = BeautifulSoup(r.content, 'html.parser')
    data = {}
    for i in bs.findAll('input'):
        data[i['name']] = i['value']
    if not data:
        return
    r = s.post(bs.find('form')['action'], data=data, verify=False)
    logger.debug("access to url %s resulting in %s" % (url, r.status_code))
    return requests_retry_session(session=s)


def init_logging(debug=0):
    levels = (
        (logging.WARNING, logging.WARNING),
        (logging.INFO, logging.WARNING),
        (logging.DEBUG, logging.WARNING),
        (logging.DEBUG, logging.INFO),
        (logging.DEBUG, logging.DEBUG),
    )
    level = levels[min(debug, len(levels) - 1)]
    formatter = logging.Formatter('** %(asctime)s.%(msecs)03d %(levelname)s: '
                                  '[%(name)s] %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(level[0])
    logger.setLevel(level[0])
    logger.addHandler(handler)
    urllib3_logger = logging.getLogger('urllib3.connectionpool')
    urllib3_logger.setLevel(level[1])

def parse_args():
    '''Parse command line'''

    parser = ArgumentParser()

    parser.add_argument('-v', '--debug', action='count', default=0,
                        help='Increases verbosity')
    parser.add_argument('--url', default="https://campusvirtual.uclm.es",
                        help="Url to connect to")
    parser.add_argument('--user',
                        help="Username to be used")
    parser.add_argument('--password',
                        help="Password to be used")
    return parser.parse_args()



def main():
    options = parse_args()
    init_logging(options.debug)

    if os.path.exists("credentials"):
        with open("credentials") as fd:
            cred = json.load(fd)
    else:
        cred = dict()

    if options.user:
        cred['user'] = options.user
    if options.password:
        cred['password'] = options.password

    if not cred.get('user'):
        cred['user'] = input("User? ")
    if not cred.get('password'):
        cred['password'] = getpass.getpass("Password? ")

    while True:
        try:
            session = getsession(options.url, cred['user'], cred['password'])
            break
        except InvalidPassword:
            print("Invalid credentials or connection timeout!")
            print("Try again:")
            cred['user'] = cinput("User? ")
            cred['password'] = getpass.getpass("Password? ")
    moodle = Moodle(session, options.url)
    shell = MoodleShell(moodle)
    shell.cmdloop()


if __name__ == '__main__':
    main()
