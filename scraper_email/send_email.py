import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.message import EmailMessage
from typing import List
# from scraper_email.gmail_info import GmailLogin

class SendEmail:
    def __init__(self, gmail_info, property_website):
        with open(gmail_info) as f:
            config = json.load(f)
            self._gmail_user = config.get('gmail_user')
            self._gmail_password = config.get('gmail_password')
            self._from_addr = config.get('from_addr')
            self._bcc_addr = config.get('bcc_addr')
            self._to_addr = config.get('to_addr')

        self.article_updated = ""
        self.arcticle_new = ""

        self.property_website = property_website

    @property
    def update_property(self)-> List:
        return self._update_property

    @update_property.setter
    def update_property(self, value):
        self._update_property = value

    @property
    def new_property(self)-> List:
        return self._new_property

    @new_property.setter
    def new_property(self, value):
        self._new_property = value
    
    def send_email(self):
        """Sends the email containing articles to the list of recipients

        Args:
            html_msg (str): html str of email
        """    
        msg = EmailMessage()
        msg.set_content("body of email")

        #Setup the MIME
        message = MIMEMultipart('alternative')
    
        message['From'] = self._from_addr
        message['To'] = ", ".join(self._to_addr)
        message['Subject'] = 'New Properties found.'   #The subject line
        
        #The body and the attachments for the mail
        message.attach(MIMEText(
            self.build_html(), 'html')
            )
        #Create SMTP session for sending the mail
        session = smtplib.SMTP('smtp.gmail.com', 587) #use gmail with port
        session.starttls() #enable security
        session.login(self._gmail_user, self._gmail_password) #login with mail_id and password
        text = message.as_string()
        session.sendmail(self._from_addr, self._to_addr + self._bcc_addr, text)
        session.quit()
        print('Mail Sent')

    def article_html_updated(self):
        """Builds the html string to be emailed. Takes news articles scraped and
        formats it into html

        Args:
            news_provider (str): The news source scraped from
            headline_titles (list): List of titles of scraped articles
            summaries (list): Summary of scraped articles
            dates (list): Hours since articles published
            links (list): Links to articles

        Returns:
            [str]: Data formatted in html
        """
        self.article_updated = self.article_updated + f'<h2>{self.property_website}</h2>'
        if not self._update_property:
            self.article_updated = self.article_updated + f'<p>No New Price changes found</p>'

        for property_dict in self._update_property:
            timestamp = property_dict['timestamp']
            link = property_dict['link']
            address = property_dict['address']
            image = property_dict['image']
            description = property_dict['description']
            price_change = property_dict['price_change']
            price = property_dict['updated_price']
            old_price = property_dict['old_price']
            price_history  = [
                f'<li>Time: {x[0]} UTC Price: £{x[1]}</li>' for x in property_dict['price_history']
                ]

            self.article_updated = self.article_updated + (
                f'<a href={link}><h3>{address}</h3></a>'
                f'Updated: {timestamp} UTC'
                f'<h4>{round(price_change, 1)}% Price Decrease</h4>'
                f'<p>Price: <span style="color:red"><strike>£{old_price}</strike></span> \
                    £{price} PCM (-{round(price_change, 1)}% )</p>'
                f'<ul>'
                f'{"".join(price_history)}'
                f'</ul>'
                f'<img src="{image}" alt="Property Photo" style="width:476px;height:317px;">'
                f'<p>{description}<br>'
                f'<br>'
            )

    def article_html_new(self):
        """Builds the html string to be emailed. Takes news articles scraped and
        formats it into html

        Args:
            news_provider (str): The news source scraped from
            headline_titles (list): List of titles of scraped articles
            summaries (list): Summary of scraped articles
            dates (list): Hours since articles published
            links (list): Links to articles

        Returns:
            [str]: Data formatted in html
        """
        self.arcticle_new = self.arcticle_new + f'<h2>{self.property_website}</h2>'
        if not self._new_property:
            self.art = self.arcticle_new + f'<p>No New properties found</p>'
        for property_dict in self._new_property:
            timestamp = property_dict['timestamp']
            link = property_dict['link']
            address = property_dict['address']
            image = property_dict['image']
            description = property_dict['description']
            price = property_dict['price']

            self.arcticle_new = self.arcticle_new + (
                f'<a href={link}><h3>{address}</h3><a>'
                f'Updated: {timestamp} UTC'
                f'<p>Price: £{price} PCM<p>'
                f'<img src="{image}" alt="Property Photo" style="width:476px;height:317px;">'
                f'<p>{description}<br>'
                f'<br>'
            )

    def build_html(self):
        """Base structure of html str

        Args:
            article_html_str (str): Formatted html str of scraped articles

        Returns:
            [str]: Html of message to be emailed
        """
        # Build updated property html
        self.article_html_updated()
        # Build new property html
        self.article_html_new()

        html = (
        f'<html>'
            f'<head></head>'
            f'<body>'
                f'<h2>Propety price changes</h2>'
                f'{self.article_updated}'
                f'<h2>New Property</h2>'
                f'{self.arcticle_new}'
            f'</body>'
        f'</html>'
        )

        return html

### Example usage ###
# send_email = SendEmail('Rightmove')

# send_email.update_property = []
# send_email.new_property = []
# send_email.send_email()
