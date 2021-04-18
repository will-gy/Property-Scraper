"""Sends an email summarising articles scraped from sources within the 
previous 24 hours

codeauthor:: William Yelverton
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.message import EmailMessage
from rightmove_scraper_zone2 import manage_rightmove


def send_email(html_msg):
    """Sends the email containing articles to the list of recipients

    Args:
        html_msg (str): html str of email
    """    
    msg = EmailMessage()
    msg.set_content("body of email")

    gmail_user = 'PLACEHOLDER@gmail.com'
    from_addr = f"Propety Web Scraper <{gmail_user}>"
    to_addr = ["john.smith@gmail.com"]

    gmail_password = 'PLACEHOLDER'

    #Setup the MIME
    message = MIMEMultipart('alternative')
 
    message['From'] = from_addr
    message['To'] = ", ".join(to_addr)
    message['Subject'] = 'New Properties found.'   #The subject line
    
    #The body and the attachments for the mail
    message.attach(MIMEText(html_msg, 'html'))
    #Create SMTP session for sending the mail
    session = smtplib.SMTP('smtp.gmail.com', 587) #use gmail with port
    session.starttls() #enable security
    session.login(gmail_user, gmail_password) #login with mail_id and password
    text = message.as_string()
    session.sendmail(from_addr, to_addr, text)
    session.quit()
    print('Mail Sent')


article_html_str_updated = ""
article_html_str_new = ""
def article_html_updated(propety_website, updated_property_list):
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
    global article_html_str_updated

    article_html_str_updated = article_html_str_updated + f'<h2>{propety_website}</h2>'
    if len(updated_property_list) == 0:
        article_html_str_updated = article_html_str_updated + f'<p>No New Price changes found</p>'
    for property_dict in updated_property_list:
        link = property_dict['link']
        address = property_dict['address']
        image = property_dict['image']
        description = property_dict['description']
        price_change = property_dict['price_change']
        price = property_dict['updated_price']
        #old_price = property_dict['old_price']
        #title_trimmed = title.split('\n')[0]
        article_html_str_updated = article_html_str_updated + (
            f'<a href={link}><h3>{address}</h3></a>'
            f'<h4>{round(price_change, 1)}% Price Decrease</h4>'
            f'<p>New Price: £{price} PCM</p>'
            #f'<p>Old Price: £{old_price} PCM</p>'
            f'<img src="{image}" alt="Property Photo" style="width:476px;height:317px;">'
            f'<p>{description}<br>'
            f'<br>'
        )

def article_html_new(propety_website, new_property_list):
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
    global article_html_str_new

    article_html_str_new = article_html_str_new + f'<h2>{propety_website}</h2>'
    if len(new_property_list) == 0:
        article_html_str_new = article_html_str_new + f'<p>No New properties found</p>'
    for property_dict in new_property_list:
        link = property_dict['link']
        address = property_dict['address']
        image = property_dict['image']
        description = property_dict['description']
        price = property_dict['price']
        #title_trimmed = title.split('\n')[0]
        article_html_str_new = article_html_str_new + (
            f'<a href={link}><h3>{address}</h3><a>'
            f'<p>Price: £{price} PCM<p>'
            f'<img src="{image}" alt="Property Photo" style="width:476px;height:317px;">'
            f'<p>{description}<br>'
            f'<br>'
        )

        #return article_html


def build_html():#article_html_str_updated, article_html_str_new):
    """Base structure of html str

    Args:
        article_html_str (str): Formatted html str of scraped articles

    Returns:
        [str]: Html of message to be emailed
    """    
    html = (
    f'<html>'
        f'<head></head>'
        f'<body>'
            f'<h2>Propety price changes</h2>'
            f'{article_html_str_updated}'
            f'<h2>New Property</h2>'
            f'{article_html_str_new}'
        f'</body>'
    f'</html>'
    )

    return html


if __name__ == '__main__':
    updated_property_list, new_property_list = manage_rightmove('rightmove_zone2')
    article_html_updated('Rightmove', updated_property_list)
    article_html_new('Rightmove', new_property_list)#, new_property_list)
    html_msg = build_html()#updated_property_list)
    send_email(html_msg)
