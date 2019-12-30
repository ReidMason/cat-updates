import os
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
import json
import smtplib

# Email credentials
import schedule as schedule

MY_ADDRESS = os.environ.get('MY_ADDRESS')
PASSWORD = os.environ.get('PASSWORD')
RECIPIENT = os.environ.get('RECIPIENT')


def log(text: str) -> None:
    """ Logs text with a specified style using colorama styles """
    timestamp = datetime.today().strftime('%d-%m-%Y %H:%M:%S')
    print(f"{timestamp} {text}")


def map_living_with_cats(living_with_cats):
    mapping = {''                      : 'Unknown',
               'B - Not To Live With'  : 'I prefer not to live with other cats',
               'A - Possibly Live With': 'I may be able to live with other cats'
               }

    return mapping.get(living_with_cats, living_with_cats.split('-')[-1].strip())


def generate_cats_display_html(data, heading):
    if len(data) == 0:
        return ''

    # Add the image as an html embed
    html = f"""<h1 style="margin-bottom: 0px;">{heading}</h1><hr><table>"""
    for i, cat in enumerate(data):
        status = cat.get('field_animal_reserved')
        if status == '':
            status = cat.get('field_animal_rehomed')

        html += f"""<tr style="{'margin-top: 20px;' if i > 0 else ''}">
                        <a href="https://www.battersea.org.uk{cat.get('path')}">
                            <img style="padding-right: 30px;" src="{cat.get('field_animal_thumbnail')}" >
                        </a>
                        <td>
                        <div style="padding-bottom: 70%;">
                           
                            <a href="https://www.battersea.org.uk{cat.get('path')}">
                                <h1 style="margin: 0px; margin-top: 20px;" href="https://www.battersea.org.uk{cat.get('path')}">{cat.get('title')}</h1>
                            </a>                        
                            <hr style="margin-bottom: 10px;">
                            <h3 style="margin-bottom: 10px; margin-top: 0px; margin-bottom: 5px;">{cat.get('age')}</h3>
                            <h3 style="margin-bottom: 10px; margin-top: 0px; margin-bottom: 5px; color: {'Orange' if status == 'Reserved' else 'Green'}">{status}</h3>
                            <h3 style="margin-bottom: 10px; margin-top: 0px; margin-bottom: 5px;">{cat.get("field_animal_sex")}</h3>
                            <h3 style="margin-bottom: 10px; margin-top: 0px; margin-bottom: 5px;">{map_living_with_cats(cat.get("field_animal_cat_suitability"))}</h3>
                            <h3 style="margin-bottom: 10px; margin-top: 0px; margin-bottom: 5px;">Location: {cat.get("field_animal_centre").title()}</h3>
                            <h3 style="margin-bottom: 10px; margin-top: 0px; margin-bottom: 5px;">Date added: {cat.get("field_animal_date_published")}</h3>
                        </div>
                        </td>
                        </tr>"""
    html += """</table>"""

    return html


def send_email(new_cats, reserved_cats, unreserved_cats, rehomed_cats, removed_cats, ):
    # Create the connection to the mail server
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.ehlo()
    server.starttls()
    server.login(MY_ADDRESS, PASSWORD)

    # Create the header for the email with the subject to and from etc
    msg = MIMEMultipart('related')

    msg['Subject'] = 'New cat alert!' if len(new_cats) > 0 else 'Cat updates!'
    msg['From'] = MY_ADDRESS
    msg['To'] = RECIPIENT

    # Add the message body
    msg_alternative = MIMEMultipart('alternative')
    msg.attach(msg_alternative)

    html = generate_cats_display_html(new_cats, 'New Cats')
    html += generate_cats_display_html(reserved_cats, 'Reserved Cats')
    html += generate_cats_display_html(unreserved_cats, 'Unreserved Cats')
    html += generate_cats_display_html(rehomed_cats, 'Re-homed Cats')
    html += generate_cats_display_html(removed_cats, 'Removed Cats')
    msg_text = MIMEText(html, 'html')
    msg_alternative.attach(msg_text)

    server.sendmail(MY_ADDRESS, RECIPIENT, msg.as_string())
    server.close()


def add_age_to_cat_data(cat_data):
    now = datetime.now()
    for cat in cat_data:
        birth_date = datetime.strptime(cat.get('field_animal_age'), '%Y-%m-%d')
        years = now.year - birth_date.year
        years = f'{years} year{"s" if years > 1 else ""} ' if years > 0 else ""

        months = now.month - birth_date.month
        months = f'{months} month{"s" if months > 1 else ""}' if months > 0 else ""

        cat['age'] = f'{years}{months} old'

    return cat_data


def check_for_new_cats(new_cat_data, old_cat_data):
    new_cats = []
    old_cat_ids = [x.get('nid') for x in old_cat_data]
    for cat in new_cat_data:
        if cat.get('nid') not in old_cat_ids:
            new_cats.append(cat)

    return new_cats


def check_for_reserved_cats(new_cat_data, old_cat_data):
    reserved_cats = []
    unreserved_cats = []

    for cat in new_cat_data:
        id = cat.get('nid')
        cat_reserved = cat.get('field_animal_reserved')
        for old_cat in old_cat_data:
            old_cat_reserved = old_cat.get('field_animal_reserved')
            if old_cat.get('nid') == id and cat_reserved != '' and old_cat_reserved == '':
                reserved_cats.append(cat)

            elif old_cat.get('nid') == id and cat_reserved == '' and old_cat_reserved != '':
                unreserved_cats.append(cat)

    return reserved_cats, unreserved_cats


def check_for_rehomed_cats(new_cat_data, old_cat_data):
    rehomed_cats = []

    for cat in new_cat_data:
        id = cat.get('nid')
        cat_rehomed = cat.get('field_animal_rehomed')
        for old_cat in old_cat_data:
            old_cat_rehomed = old_cat.get('field_animal_rehomed')
            if old_cat.get('nid') == id and cat_rehomed != '' and old_cat_rehomed == '':
                rehomed_cats.append(cat)

    return rehomed_cats


def check_for_removed_cats(new_cat_data, old_cat_data):
    for cat in new_cat_data:
        id = cat.get('nid')
        for i, old_cat in enumerate(old_cat_data):
            if old_cat.get('nid') == id:
                old_cat_data.pop(i)
                break

    return old_cat_data


def run_cat_check():
    log("Running cat check")
    r = requests.get('https://www.battersea.org.uk/api/animals/cats')
    new_cat_data = json.loads(r.content).get('animals')

    if os.path.exists('data/old_cat_data.json'):
        with open('data/old_cat_data.json', 'r') as f:
            old_cat_data = json.load(f)

        new_cat_data = add_age_to_cat_data(new_cat_data)
        old_cat_data = add_age_to_cat_data(old_cat_data)

        new_cats = check_for_new_cats(new_cat_data, old_cat_data)
        reserved_cats, unreserved_cats = check_for_reserved_cats(new_cat_data, old_cat_data)
        rehomed_cats = check_for_rehomed_cats(new_cat_data, old_cat_data)
        removed_cats = check_for_removed_cats(new_cat_data, old_cat_data)

        if not len(new_cats) == 0:
            log("Update detected. Sending email")
            send_email(new_cats, reserved_cats, unreserved_cats, rehomed_cats, removed_cats)
            with open('data/old_cat_data.json', 'w') as f:
                json.dump(new_cat_data, f)
        else:
            log("No new updates")

    else:
        with open('data/old_cat_data.json', 'w') as f:
            json.dump(new_cat_data, f)
    log("Check complete")


if __name__ == '__main__':
    schedule.every(20).minutes.do(lambda: run_cat_check())
    run_cat_check()

    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print(e)

        time.sleep(60)
