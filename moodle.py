import cmd
import sys
import argparse
import json
import logging
import re
import os
import sys
import urllib3
import getpass
import requests
from bs4 import BeautifulSoup


# python 2 and 3 compatible input
cinput = input if sys.version_info[0] == 3 else raw_input

# avoid annoying warnings from SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger()


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


class MoodleShell(cmd.Cmd):
    intro = """
Now you are logged in.
Next steps:
- Run "select" to select a subject. It allows completion.
- Then run "download" to download a module. No arguments to download them all.
    """
    def __init__(self, session, url, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subject = None
        self.session = session
        self.url = url

    def download(self, url):
        mock = False
    #    mock = True
        if mock:
            with open("example_moodle.html") as fd:
                return Parser(fd.read())
        if url.startswith('/'):
            url = self.url + url
        r = self.session.get(url, verify=False)
        return Parser(r.content)
   
    def download_subject(self, id, path):
        logger.debug("Selecting section with id = %s" % id)
        if not os.path.exists(path):
            os.makedirs(path)
        parser = self.download(self.subject['href'])
        content = parser.find(id=id)
        if not content:
            logger.info("Subject without content: %s" % id)
            return
        for link in content.findAll('a'):
            href = link['href']
            for i in link.findAll('', {'class': 'accesshide'}):
                try:
                    i.remove()
                except:
                    pass
            title = link.text.strip()
            if '#' in href:
                logging.info("Ignoring link to %s" % title)
                continue
            self.download_link(href, title, path)
        #print(content)

    def download_link(self, url, title, path):
        logger.warning("Downloading %s" % title)
        r = self.session.get(url, verify=False)
        cd = r.headers.get("Content-Disposition", '')
        m = re.match('.*filename="(.*?)".*', cd)
        filename = m.group(1) if m else title
        logger.warning("Downloading file %s" % filename)
        with open(os.path.join(path, filename), 'bw+') as fd:
            fd.write(r.content)
        logger.warning("File %s downloaded" % filename)

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
            p = self.download("/my/")
            result = []
            for title, href in (p.course_list()):
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
        path = input("Output path? ")
        if not arg or arg == '_EVERYTHING_':
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
            p = self.download(self.subject['href'])
            
            result = []
            if not text or text.upper() in '_EVERYTHING_':
                result.append('_EVERYTHING_')
            for title, href in (p.module_list()):
                _title = title.replace(" ", "_")
                if text and text.lower() not in _title.lower():
                    continue
                url, _, id = href.partition('#')
                result.append(_title)
                self.choices[_title] = id
            return result
        except Exception as e:
            print(e)

    def help_download(self):
        print("Downloads a module or subject")

    def do_EOF(self, arg):
        return True

    def help_EOF(self):
        print("Exit program. Shortcut: CTRL+D")


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
    r = s.post(r.url, data=data, verify=False)
    bs = BeautifulSoup(r.content, 'html.parser')
    data = {}
    for i in bs.findAll('input'):
        data[i['name']] = i['value']
    if not data:
        return
    r = s.post(bs.find('form')['action'], data=data, verify=False)
    return s 

def main():
    url = "https://campusvirtual.uclm.es"
    if os.path.exists("credentials"):
        with open("credentials") as fd:
            cred = json.load(fd)
    else:
        cred = dict()
    
    if not cred.get('user'):
        cred['user'] = cinput("User? ")
    if not cred.get('password'):
        cred['password'] = getpass.getpass("Password? ")

    session = getsession(url, cred['user'], cred['password'])
    
    shell = MoodleShell(session, url)
    shell.cmdloop()


if __name__ == '__main__':
    main()
