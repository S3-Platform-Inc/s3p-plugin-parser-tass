import copy
import time
from datetime import datetime
from typing import Iterator

# import dateparser
import dateutil.parser
import feedparser
from s3p_sdk.exceptions.parser import S3PPluginParserOutOfRestrictionException, S3PPluginParserFinish
from s3p_sdk.plugin.payloads.parsers import S3PParserBase
from s3p_sdk.types import S3PRefer, S3PDocument, S3PPlugin, S3PPluginRestrictions
from s3p_sdk.types.plugin_restrictions import FROM_DATE
import requests
from bs4 import BeautifulSoup
from random import randint


class TASS(S3PParserBase):
    """
    A Parser payload that uses S3P Parser base class.
    """

    def __init__(self, refer: S3PRefer, plugin: S3PPlugin, restrictions: S3PPluginRestrictions, feeds: list[str, ...]):
        super().__init__(refer, plugin, restrictions)

        # Тут должны быть инициализированы свойства, характерные для этого парсера. Например: WebDriver
        self.feeds = feeds
        self.headers = {"Accept-Language": "ru,en;q=0.9",
           "Accept-Encoding": "gzip, deflate, br, zstd",
           "Sec-Fetch-Dest": "document",
           "Sec-Fetch-Mode": "navigate",
           "Sec-Fetch-Site": "cross-site",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
           "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 YaBrowser/25.2.0.0 Safari/537.36"}

    def _parse(self):
        """
        Парсер сначала получает document из фидов. После запроса страницы передаёт в document.other
        словарь "general", куда добавляется текст, возвращаемый find_text, а затем словарь
        "additionals_dict", возвращаемый find_additions.
        """
        if isinstance(self._restriction.maximum_materials, int) and self._restriction.maximum_materials // len(
                self.feeds) >= 2:
            number = self._restriction.maximum_materials // len(self.feeds) + 1
        else:
            number = None

        for feed in self.feeds:
            for document in self._slices(
                self._rss_feed(feed),
                number
            ):
                time.sleep(randint(1,3))
                parsed_document = self._parsed_webpage(document)
                try:
                    parsed_document.loaded = datetime.now()
                    self._find(parsed_document)
                except S3PPluginParserOutOfRestrictionException as e:
                    self.logger.warning(f"Document {parsed_document.link} is outside the specified date range")
                    if e.restriction == FROM_DATE:
                        break
                except S3PPluginParserFinish as e:
                    raise e

    def _slices(self, feed: Iterator[S3PDocument], number: int | None = None) -> Iterator[S3PDocument]:
        for current, element in enumerate(feed):
            if number is not None and current >= number:
                break
            yield element

    def _rss_feed(self, url: str) -> Iterator[S3PDocument]:
        """
        url: str: RSS FEED url
        """
        # Parse the Finextra RSS feed
        feed = feedparser.parse(url)

        if len(feed.entries) <= 0:
            raise ValueError(f'RSS feed {url} is empty')

        # Iterate through feed entries
        for entry in feed.entries:
            parsed_date = dateutil.parser.parse(entry.published)

            if 'tass.ru/nauka' in entry.link:
                continue

            yield S3PDocument(
                None,
                entry.title,
                None,
                None,
                entry.link,
                None,
                {
                    'summary': entry.summary if 'summary' in entry else None,
                },
                parsed_date.replace(tzinfo=None),
                None
            )

    def _parsed_webpage(self, document: S3PDocument) -> S3PDocument | None:
        #Делаем запрос к странице
        response = requests.get(document.link, headers=self.headers)
        if response.status_code != 200:
            raise ConnectionError(f"Failed to access {document.link} page. Status code: {response.status_code}")

        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        try:
            return TASS.ArticlePage(soup, document).document()
        except TASS.PageException:
            ...

        try:
            return TASS.NaukaPage(soup, document).document()
        except TASS.PageException:
            ...

        raise ValueError(f'{document.link} not parsed. Profile is not exist')

    class PageException(Exception):

        def __init__(self, profile, message, errors=None):
            super().__init__(message)
            self.errors = errors
            self.profile = profile
            self.message = message

        def __repr__(self):
            return f"Profile {type(self.profile)} Not found"

    class ArticlePage:
        # META: str = 'Article'

        def __init__(self, soup, document: S3PDocument):
            self.soup = soup
            self.doc = copy.deepcopy(document)
            # self.doc.other['type'] = self.META

        def document(self) -> S3PDocument:
            # Main article text
            article_body = self.soup.find('article')
            if article_body is None:
                raise TASS.PageException(self, f'', None)
            else:
                article_text = article_body.get_text(strip=True) # '\n'.join([p.get_text(strip=True) for p in article_body.find_all('p')])
                self.doc.text = article_text

            # Abstract field
            if self.doc.other['summary'] is not None:
                self.doc.abstract = self.doc.other['summary']
            else:
                self.doc.abstract = article_body.find_all('p')[0].get_text(strip=True)


            # Additional fields
            # types_additions = ['company', 'channel', 'keyword']
            # additional_section = self.soup.find('div', class_='additional-info')
            # additional_dict = {}
            # if additional_section is not None:
            #     for addition_name in types_additions:
            #         # Проверяем, существует ли хотя бы один элемент с классом .info-icon.{addition_name}
            #         elements = additional_section.select(f'.info-icon.{addition_name} a')
            #         if elements:  # Если список не пуст
            #             additional_dict[addition_name] = [a.get_text(strip=True) for a in elements]
            #     if additional_dict != {}:
            #         self.doc.other['general'] = additional_dict

            return self.doc

    class NaukaPage:
        # META: str = 'Article'

        def __init__(self, soup, document: S3PDocument):
            self.soup = soup
            self.doc = copy.deepcopy(document)
            # self.doc.other['type'] = self.META

        def document(self) -> S3PDocument:
            # Main article text
            article_body = self.soup.find('div', class_='text-content')
            if article_body is None:
                raise TASS.PageException(self, f'', None)
            else:
                article_text = article_body.get_text(strip=True) # '\n'.join([p.get_text(strip=True) for p in article_body.find_all('p')])
                self.doc.text = article_text

            # Abstract field
            if self.doc.other['summary'] is not None:
                self.doc.abstract = self.doc.other['summary']
            else:
                self.doc.abstract = self.soup.find('div', class_={'news-header__lead'}).get_text(strip=True)


            # Additional fields
            # types_additions = ['company', 'channel', 'keyword']
            # additional_section = self.soup.find('div', class_='additional-info')
            # additional_dict = {}
            # if additional_section is not None:
            #     for addition_name in types_additions:
            #         # Проверяем, существует ли хотя бы один элемент с классом .info-icon.{addition_name}
            #         elements = additional_section.select(f'.info-icon.{addition_name} a')
            #         if elements:  # Если список не пуст
            #             additional_dict[addition_name] = [a.get_text(strip=True) for a in elements]
            #     if additional_dict != {}:
            #         self.doc.other['general'] = additional_dict

            return self.doc

