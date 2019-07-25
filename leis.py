import csv
import requests as req

from bs4 import BeautifulSoup
from decouple import config
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver import Firefox
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from tqdm import tqdm

from commons import striphtml
from urls import urls_decretos_planalto, urls_leis_ordinarias_planalto


class Planalto:
    base_url = "http://www4.planalto.gov.br/legislacao/portal-legis/"\
               "legislacao-1/"

    def __init__(self):
        self.driver = Firefox(executable_path=config('DRIVER_PATH'))

    def get_content(self, link):
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X'
                   '10_10_1) Appl eWebKit/537.36 (KHTML, like Gecko)'
                   'Chrome/39.0.2171.95Safari/537.36'
                   }
        resp = req.get(link, headers=headers)
        content = resp.content.decode('latin-1')
        return BeautifulSoup(content, features='lxml').find('body').text

    def get_row_info(self, tds, year):
        try:
            link = tds[0].find_element_by_tag_name('a').get_attribute('href')
            inteiro_teor = striphtml(self.get_content(link))
        except NoSuchElementException:
            inteiro_teor = ''

        info = {k: v.text for k, v in zip(('lei', 'ementa'), tds)}
        info['ano'] = year
        info['inteiro_teor'] = inteiro_teor
        return info

    def extract_info(self, year, url):
        download_desc = 'Baixando {tipo} Planalto ({ano})'.format(
            tipo=self.tipo_lei,
            ano=year
        )
        with open(self.file_destination, 'w', newline='') as csvfile:
            writer = csv.DictWriter(
                csvfile,
                fieldnames={'lei', 'ementa', 'ano', 'inteiro_teor'},
                delimiter=";",
                quotechar='"'
            )
            writer.writeheader()

            self.driver.get(self.base_url + url)
            wait = WebDriverWait(self.driver, 20)
            wait.until(EC.presence_of_element_located(
                (By.TAG_NAME, 'table')
                )
            )
            table = self.driver.find_element_by_tag_name('table')
            rows = table.find_elements_by_tag_name('tr')

            # rows[1:] to skip table header
            for row in tqdm(rows[1:], desc=download_desc):
                tds = row.find_elements_by_tag_name('td')
                row_info = self.get_row_info(tds, year)
                writer.writerow(row_info)

    def download(self):
        for year, url in self.urls.items():
            self.extract_info(year, url)


class DecretosPlanalto(Planalto):
    def __init__(self, file_destination):
        super().__init__()
        self.file_destination = file_destination
        self.tipo_lei = 'decretos'
        self.urls = urls_decretos_planalto


class LeisOrdinariasPlanalto(Planalto):
    def __init__(self, file_destination):
        super().__init__()
        self.file_destination = file_destination
        self.tipo_lei = 'leis ordinárias'
        self.urls = urls_leis_ordinarias_planalto


class LeisComplementaresPlanalto(Planalto):
    def __init__(self, file_destination):
        super().__init__()
        self.file_destination = file_destination
        self.tipo_lei = 'leis complementares'
        self.urls = {
            'todos-os-anos': 'leis-complementares-1/'
                             'todas-as-leis-complementares-1'
        }


class Alerj:

    dns = "http://alerjln1.alerj.rj.gov.br"
    base_url = dns + "/contlei.nsf/{tipo}?OpenForm&Start={start}&Count=1000"
    header = ['lei', 'ano', 'autor', 'ementa']

    def __init__(self, file_destination):
        self.file_destination = file_destination

    def visit_url(self, start):
        url = self.base_url.format(tipo=self.tipo, start=start)
        common_page = req.get(url)
        soup = BeautifulSoup(common_page.content, features='lxml')
        return soup.find_all('tr')

    def parse_metadata(self, row):
        columns = row.find_all('td')
        return dict(zip(self.header, [c.text for c in columns]))

    def parse_full_content(self, row):
        full_content_link = self.dns + row.find('a')['href']
        resp = req.get(full_content_link)
        soup = BeautifulSoup(resp.content, features='lxml')
        body = soup.find('body')
        return striphtml(body.text)

    def download(self):
        download_desc = 'Baixando {tipo} Alerj'.format(
            tipo=self.tipo_lei
        )
        with open(self.file_destination, 'w', newline='') as csvfile:
            writer = csv.DictWriter(
                csvfile,
                fieldnames=['lei', 'ano', 'autor', 'ementa', 'inteiro_teor'],
                delimiter=";",
                quotechar='"'
            )
            writer.writeheader()

            page = 1
            rows = self.visit_url(start=page)
            while len(rows):
                # Skip header
                for row in tqdm(rows[1:], desc=download_desc):
                    metadata = self.parse_metadata(row)
                    metadata['inteiro_teor'] = self.parse_full_content(row)
                    writer.writerow(metadata)

                start = page * 1000 + 1
                page += 1
                rows = self.visit_url(start)


class DecretoAlerj(Alerj):
    tipo = 'DecretoInt'
    tipo_lei = 'decretos'
