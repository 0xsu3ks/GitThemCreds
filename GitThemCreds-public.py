#/usr/bin/python3
import requests
import time
import sys
import json
import argparse
import yaml
from colorama import init, Fore


parser = argparse.ArgumentParser(description='GitHub API Code Search')
parser.add_argument('--domain', type=str, help='Domain name to search on GitHub', required=True)

args = parser.parse_args()

#What's a tool without a banner?
with open('banner', 'r') as f:
	for line in f:
		print(line.rstrip())
print('\n')

#Initializing all the things

with open('config-public.yaml', 'r') as stream:
    try:
        config = yaml.safe_load(stream)
        print('\n[+] Config loaded!\n')
    except yaml.YAMLError as exc:
        print(exc)
github_token = config['github_pat']
queries = config['queries']
with open('output.json', 'w') as f1, open('urls.txt', 'w') as f2:
    pass

#Dirty function to grab dorks from config file
def getQueryParameters(filename):
    with open(filename, 'r') as file:
        data = yaml.safe_load(file)
        queries = data['queries']
        for query in queries:
            yield query

domain = args.domain
filename = '.config.yaml'
keywords = getQueryParameters(filename)
keywords_generator = getQueryParameters(filename)

#Pagination tracker variable
page = 1

#Colors because why not?
print(Fore.GREEN + "========================== Starting GitHub API Code Search ==========================")

#Meat and Potatoes
#I will break this down as best as I can

#This is a for loop over all our dorks loaded from the configuration file
for query in keywords:

    #This allows us to take that keyword and look at different pages from the API call
    for page in range(1, 2):
        #Building our URL with the proper headers
        #This may break if version changes, issues authenticating check
        #https://docs.github.com/en/rest/overview/authenticating-to-the-rest-api?apiVersion=2022-11-28
        url = f'https://api.github.com/search/code?q={domain}+{query}&page={page}'
        headers = {
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'Authorization': f'Bearer {github_token}'
        }
        print('\n' + Fore.YELLOW + '[+] Git Search URL: ' + Fore.YELLOW + f'{url}')

        #Try and catch all the errors! Print out the API errors to terminal but to not output
        try:
            #Simple GET request here
            response = requests.get(url, headers=headers)
            response_json = response.json()

            #Now the annoying part
            #For loop to put the repository URL but we need to add the .git suffix
            
            if not response_json['items']:
                print(f'\t- No repositories found')
            else:
                for item in response_json['items']:
                    repo_url = item['repository']['html_url']
                    print(f'\t- Repository found: {repo_url}.git')

        #API error handling like a boss, lots of repeat code, create functions I know
        except Exception as e:
            #If we get an API error
            print(Fore.RED + f'[!] API Error: {response.text}')


        
            for item in response_json['items']:
                repo_url = item['repository']['html_url']
                print(f'\t- Repository found: {repo_url}.git')




