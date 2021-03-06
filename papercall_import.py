from os import makedirs
from os.path import exists

from envparse import env
import frontmatter
from requests import get
from slugify import slugify
from xlwt import easyxf, Workbook

# Possible proposal states that we need
PROPOSAL_STATES = ('accepted',)

# Style for the Spreadsheet headers
HEADER_STYLE = easyxf(
    'font: name Verdana, color-index blue, bold on',
    num_format_str='#,##0.00'
)


def get_api_key():
    """
    Get the user's API key
    """
    print('Your PyGotham PaperCall API Key can be found here: https://www.papercall.io/events/534/apidocs')
    api_key = input('Please enter your PaperCall event API Key: ')
    if len(api_key) != 32:
        raise ValueError('Error: API Key must be 32 characters long.')

    return api_key


def get_format():
    """
    Get the output format to write to.
    """
    print('Which format would you like to output?')
    print('1: Excel')
    print('2: YAML/Markdown for Jekyll')
    file_format = input('Please enter your your output format (1 or 2): ')
    if file_format not in ('1', '2'):
        raise ValueError('Error: Output format must be "1" or "2".')

    return file_format


def get_filename(input_text, default_filename):
    # Get file name from user
    output_filename = input(input_text) or default_filename

    return output_filename


def create_excel(api_key, xls_file):
    # Create the Spreadsheet Workbook
    wb = Workbook()

    for proposal_state in PROPOSAL_STATES:
        # Reset row counter for the new sheet
        # Row 0 is reserved for the header
        num_row = 1

        # Create the new sheet and header row for each talk state
        ws = wb.add_sheet(proposal_state.upper())
        ws.write(0, 0, 'ID', HEADER_STYLE)
        ws.write(0, 1, 'Title', HEADER_STYLE)
        ws.write(0, 2, 'Format', HEADER_STYLE)
        ws.write(0, 3, 'Audience', HEADER_STYLE)
        ws.write(0, 4, 'Rating', HEADER_STYLE)
        ws.write(0, 5, 'Name', HEADER_STYLE)
        ws.write(0, 6, 'Bio', HEADER_STYLE)

        for x in range(7, 35):
            ws.write(0, x, 'Comments / Feedback {}'.format(x - 6), HEADER_STYLE)

        r = get(
            'https://www.papercall.io/api/v1/submissions?_token={0}&state={1}&per_page=1000'.format(
                api_key,
                proposal_state,
            )
        )

        for proposal in r.json():
            ws.write(num_row, 0, proposal['id'])
            ws.write(num_row, 1, proposal['talk']['title'])
            ws.write(num_row, 2, proposal['talk']['talk_format'])
            ws.write(num_row, 3, proposal['talk']['audience_level'])
            ws.write(num_row, 4, proposal['rating'])
            ws.write(num_row, 5, proposal['profile']['name'])
            ws.write(num_row, 6, proposal['profile']['bio'])

            # Start at column 7 for comments and feedback
            num_col = 7

            # Only include ratings comments if they've been entered
            c = get(
                'https://www.papercall.io/api/v1/submissions/{}/ratings?_token={}'.format(
                    proposal['id'],
                    api_key,
                )
            )
            for ratings_comment in c.json():
                if len(ratings_comment['comments']):
                    ws.write(
                        num_row,
                        num_col,
                        '(Comment from {}) {}'.format(
                            ratings_comment['user']['email'],
                            ratings_comment['comments'],
                        ),
                    )
                    num_col += 1

            # Loop through all of the submitter / reviewer feedback and include after comments
            f = get(
                'https://www.papercall.io/api/v1/submissions/{}/feedback?_token={}'.format(
                    proposal['id'],
                    api_key,
                )
            )
            for feedback in f.json():
                ws.write(
                    num_row,
                    num_col,
                    '(Feedback from {}) {}'.format(
                        feedback['user']['email'],
                        feedback['body'],
                    ),
                )
                num_col += 1

            num_row += 1

    wb.save(xls_file)


def create_yaml(api_key, talks_dir, speakers_dir):
    if not exists(talks_dir):
        makedirs(talks_dir)
    if not exists(speakers_dir):
        makedirs(speakers_dir)

    for proposal_state in PROPOSAL_STATES:
        r = get(
            'https://www.papercall.io/api/v1/submissions?_token={0}&state={1}&per_page=1000'.format(
                api_key,
                proposal_state,
            )
        )

        speakers = {}

        for proposal in r.json():
            talk_title_slug = slugify(proposal['talk']['title'])

            post = frontmatter.loads(proposal['talk']['description'])
            post['type'] = 'talk'
            post['title'] = proposal['talk']['title']
            post['level'] = proposal['talk']['audience_level']
            post['abstract'] = proposal['talk']['abstract']
            post['speakers'] = []

            speaker_name = proposal['profile']['name']
            if '/' in speaker_name:
                speaker_name = speaker_name.split('/')
            elif ' and ' in speaker_name:
                speaker_name = speaker_name.split(' and ')
            elif ',' in speaker_name and speaker_name[-5:] != ', MBA':
                speaker_name = speaker_name.split(',')
            else:
                speaker_name = [speaker_name]

            for name in map(str.strip, speaker_name):
                speaker_slug = slugify(name)

                if speaker_slug not in speakers:
                    speakers[speaker_slug] = frontmatter.loads(
                        proposal['profile']['bio'])
                    speakers[speaker_slug]['name'] = name
                    speakers[speaker_slug]['talks'] = []

                post['speakers'].append(name)
                speakers[speaker_slug]['talks'].append(post['title'])

            talk_filename = '{}/{}.md'.format(talks_dir, talk_title_slug)
            with open(talk_filename, 'wb') as file_to_write:
                frontmatter.dump(post, file_to_write)

            print('saved {!r}'.format(talk_filename))

        for speaker_slug, speaker in speakers.items():
            speaker_filename = '{}/{}.md'.format(speakers_dir, speaker_slug)
            with open(speaker_filename, 'wb') as file_to_write:
                frontmatter.dump(speaker, file_to_write)

            print('saved {!r}'.format(speaker_filename))


def main():
    try:
        api_key = env('PAPERCALL_API_KEY')
    except:
        api_key = get_api_key()
    file_format = get_format()

    if file_format == "1":
        xls_file = get_filename('Filename to write [djangoconus.xls]: ', 'djangoconus.xls')
        create_excel(api_key, xls_file)
    elif file_format == "2":
        talks_dir = get_filename('Directory to write talks to [talks]: ', 'talks')
        speakers_dir = get_filename('Directory to write speakers to [speakers]: ', 'speakers')
        create_yaml(api_key, talks_dir, speakers_dir)


if __name__ == "__main__":
    main()
