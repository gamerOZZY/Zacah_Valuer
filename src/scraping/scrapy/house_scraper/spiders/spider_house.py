import scrapy

class SpiderHouseSpider(scrapy.Spider):
    name = "spider_house"
    allowed_domains = ["propiedades.com"]
    
    async def start(self):
        start_urls = ["https://propiedades.com/gustavo-a-madero/casas-venta"]
        for url in start_urls:
            yield scrapy.Request(
                url=url, 
                callback=self.parse,
                meta={
                    "playwright": True
                }
            )

    def parse(self, response):
        casas = response.css("section.pcom-property-card")
        urls = []

        for casa in casas[:5]:
            url = casa.css(
                "a.pcom-property-card-body-main-info-street::attr(href)"
            ).get()

            if url:
                urls.append(response.urljoin(url))

        yield {
            "url_listado": response.url,
            "urls_anuncios": urls,
        }