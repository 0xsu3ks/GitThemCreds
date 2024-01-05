#/usr/bin/python3
import requests
import time
import sys
import json
import subprocess
import argparse
import yaml
from colorama import init, Fore
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
import csv
import boto3
from botocore.config import Config
import botocore.exceptions


#What's a tool without a banner?
print('\n')
version = "2.0"
print("""  ______ __    ________               _____           __  """) 
print(""" / ___(_) /_  /_  __/ /  ___ __ _    / ___/______ ___/ /__""")
print("""/ (_ / / __/   / / / _ \/ -_)  ' \  / /__/ __/ -_) _  (_-<""")
print("""\___/_/\__/   /_/ /_//_/\__/_/_/_/  \___/_/  \__/\_,_/___/""")
print(""" 						by: @0xsu3ks                       """)
print(f"""                                                v:{version}""")


#Setting up the arguments and modules
parser = argparse.ArgumentParser(description='GitHub API Code Search with Trufflehog')
subparsers = parser.add_subparsers(dest="command", required=True)

#The enum module
enum_parser = subparsers.add_parser('enum', help='Perform enumeration of a domain')
enum_parser.add_argument('--config', type=str, help='Path to the config file', default='.config.yaml')
enum_parser.add_argument('--domain', type=str, help='Domain name to search on GitHub', required=False)
enum_parser.add_argument('--truffles', action='store_true', help='Run Trufflehog on the search results (./trufflehog git url | tee -a truffle-report.txt)')
enum_parser.add_argument('--pages', type=int, help='Number of pages to query (default: 1)', default=1)
enum_parser.add_argument('--table', action='store_true', help='Display results in a table')
enum_parser.add_argument('--check-token', type=str, help='Check if GitHub token is valid')

#In progress list:
#parser.add_argument('--organization', type=str, nargs='+', help='List of organizations to search GitHub for')
enum_parser.add_argument('--excel', action='store_true', help='Output table contents to an Excel file (in testing)')
enum_parser.add_argument('--status', action='store_true', help='Displays status bar during searching (in testing)')

#The git module
github_parser = subparsers.add_parser('git', help='Perform operations on GitHub using a token')
github_parser.add_argument('--token', type=str, help='GitHub token', required=True)
github_parser.add_argument('--repos', action='store_true', help='List repositories using the token')
github_parser.add_argument('--clone', action='store_true', help='Clone all repositories using the token')

#The bitbucket module
bitbucket_parser = subparsers.add_parser('bitbucket', help='Perform operations on Bitbucket using a token')

#The aws module
aws_parser = subparsers.add_parser('aws', help='Perform AWS checks without alerting Cloudwatch')
aws_parser.add_argument('--access-key', type=str, help='AWS Access Key', required=True)
aws_parser.add_argument('--secret-key', type=str, help='AWS Secret Access Key', required=True)
aws_parser.add_argument('--session', type=str, help='AWS Session Token', required=False)
aws_parser.add_argument('--session-url', action='store_true', help='Generate console login link', required=False)

#Parse all the args
args = parser.parse_args()

#If the ENUM module is called, run this block
if args.command == "enum":
    #We need one of these to work
    if not args.domain and not args.check_token:
        parser.error("You must provide either --domain or --check-token")

    #If --check-token is supplied, check and then exit
    def check_token(token):
        url = "https://api.github.com/user"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        response = requests.get(url, headers=headers)
        
        #Not much going on here other than checking to see if a username is returned
        if response.status_code == 200:
            print(Fore.GREEN + '[+] Valid Token!')
            output = response.json()
            login = output['login']
            admin = output['site_admin']
            print('\n' + Fore.GREEN + f'[+] Username: {login}')
            if admin == False:
                print(Fore.RED + f'[+] Admin Token: {admin}')
            else:
                print(Fore.GREEN + f'[+] Admin Token: {admin}')
            sys.exit(0)
        else:
            print(Fore.RED + '[+] Invalid Token')
            print(f'Request failed with status code {response.status_code}')
            print(response.text)
            sys.exit(1)

    if args.check_token:
        check_token(args.check_token)


    #Initializing all the things
    console = Console()
    results = []
    unique_urls = []
    init(autoreset=True)

    config_file = args.config
    with open(config_file, 'r') as stream:
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
    def get_query_parameters(filename):
        with open(filename, 'r') as file:
            data = yaml.safe_load(file)
            queries = data['queries']
            for query in queries:
                yield query

    domain = args.domain
    filename = args.config
    keywords = get_query_parameters(filename)
    keywords_generator = get_query_parameters(filename)
    keyword_count = sum(1 for _ in keywords_generator)
    #Sleep timer, yes this stinks. Every minute. This is because the GitHub API does not like us.
    #Adjust at your discretion but during testing this resulted in no errors.
    sleep = 65
    #Pagination tracker variable
    page = 1

    #Function for creating and displaying table
    def display_table(results):
        table = Table(title=f'Github Recon for {domain}', show_header=True, header_style='bold magenta')
        table.add_column('Repository URL')
        table.add_column('Query')
        table.add_column('Page')
        for repo_url, query, page in results:
            table.add_row(repo_url, query, str(page))
        console.print(table)

    #Colors because why not?
    print(Fore.GREEN + '========================== Starting GitHub API Code Search ==========================')

    #Meat and Potatoes
    #I will break this down as best as I can

    #This is a for loop over all our dorks loaded from the configuration file
    for query in keywords:

        #This allows us to take that keyword and look at different pages from the API call
        for page in range(1, args.pages + 1):
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

            #This is for printing the status bar (in testing)
            if args.status:
                with Progress() as progress:
                    task = progress.add_task('[cyan][STATUS]: ', total=keyword_count * args.pages)
                    progress.update(task, advance=1)

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

                #One way to see if we hit rate limiting (this is handled better later on)
                if 'secondary rate limit' in response.text:
                    print(f'We hit the rate limit on {query}, pausing here and restarting in 1 min.')
                    time.sleep(60)
                    response = requests.get(url, headers=headers)
                    response_json = response.json()
                    sleep += 15

                    #Repeating the above code, blasphemy I know, this probably should be a function
                    for item in response_json['items']:
                        repo_url = item['repository']['html_url']
                        print(f'\t- Repository found: {repo_url}.git')

                #Dumping output to JSON file
                with open('output.json', 'a', encoding='utf-8') as f:
                    json.dump(response_json, f, ensure_ascii=False, indent=4)

                #Dumping URLs to file
                with open('urls.txt', 'a') as f:
                    for item in response_json['items']:
                        repo_url = item['repository']['html_url']
                        f.write(f'{repo_url}.git' + '\n')

                #Similar to above but this adds the repository URL to our array
                for item in response_json['items']:
                    repo_url = item['repository']['html_url']
                    results.append((repo_url, query, page))

                #This is for creating an excel file (in testing)
                if args.excel:
                    with open('output.csv', 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([repo_url, query, str(page)])

                #We must do this, or we will hit rate limiting real quick
                time.sleep(sleep) 

                #Adding to our page counter
                if page == args.pages:
                    break
                else:
                    page +=1 

            #API error handling like a boss, lots of repeat code, create functions I know
            except Exception as e:
                #If we get an API error, it will print to terminal but then repeat the query a minute later
                print(Fore.RED + f'[!] API Error: {response.text}')
                print('\n' + Fore.CYAN + f'[+] Will retry: {url} in 60 seconds')
                time.sleep(60)
                response = requests.get(url, headers=headers)
                response_json = response.json()
                time.sleep(30)
                
                #Same as above
                for item in response_json['items']:
                    repo_url = item['repository']['html_url']
                    print(f'\t- Repository found: {repo_url}.git')

                with open('output.json', 'a', encoding='utf-8') as f:
                    json.dump(response_json, f, ensure_ascii=False, indent=4)

                with open('urls.txt', 'a') as f:
                    for item in response_json['items']:
                        repo_url = item['repository']['html_url']
                        f.write(f'{repo_url}.git' + '\n')

                #Don't hate me but we're increasing the sleep timer by 15 seconds, they're onto us!
                sleep += 15

    #Creating excel sheet (in testing)
    if args.excel:
        print(Fore.YELLOW + 'Generating Excel report...')
        with open(f'gitthemcreds-{domain}.xlsx', 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                print(row)

    #There's a better way to do this
    copy_file = 'sort -u urls.txt > unique_urls.txt'
    subprocess.run(copy_file, shell=True, check=True)

    #Displaying table to terminal
    print('\n')
    if args.table:
        display_table(results)

    #Running trufflehog on git URLs
    if args.truffles:
        print('\n' + Fore.GREEN + '========================== Starting Trufflehog ==========================')
        with open('unique_urls.txt', 'r') as f:
            for url in f:
                url = url.strip()
                command = f'./trufflehog git {url} | tee -a truffle-report.txt'
                #Need this subprocess to do this
                subprocess.run(command, shell=True, check=True)
    else:
        print('\n' + Fore.RED + '========================== Skipping Trufflehog ==========================')

elif args.command == 'git':
    repos = []
    init(autoreset=True)
    with open('repos.txt', 'w') as f3:
        pass

    token = args.token
    #For enum we will need the username, let's pull it from the API
    def check_token(token):
        url = "https://api.github.com/user"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            output = response.json()
            username = output['login']
            return username
        else:
            print(Fore.RED + '[+] Invalid Token')
            print(f'Request failed with status code {response.status_code}')
            print(response.text)
            sys.exit(1)

    def list_repos(token,username):
        url = f'https://api.github.com/search/repositories?q=user:{username}'
        headers = {
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            output = response.json()
            #print(output)

            if not output:
                print(f'\t- No repositories found')
            else:
                for item in output['items']:
                    repo_name = item['name']
                    repos.append(repo_name)
                    if item['private'] == True:
                        repo_name = item['name'] + Fore.LIGHTMAGENTA_EX + '(PRIVATE)'
                    else:
                        repo_name = item['name']
                    print(f'\t- Repo Name: {repo_name}')
            
            with open('repos.txt', 'a') as f:
                for item in output['items']:
                    repo_name = item['name']
                    f.write(f'{repo_name}' + '\n')

        else:
            print(Fore.RED + '[+] Invalid Token')
            print(f'Request failed with status code {response.status_code}')
            print(response.text)
            sys.exit(1)

    username = check_token(token)
    
    if args.token:
        print(Fore.GREEN + f'[+] Username: {username}')

    if args.repos:
        print('\n' + Fore.GREEN + '========================== Listing Repositories ==========================')
        list_repos(token,username)

        if args.clone:
            print('\n' + Fore.LIGHTBLUE_EX + '========================== Cloning Repositories ==========================')
            for repo_name in repos:
                clone_url = f'https://{username}:{token}@github.com/{username}/{repo_name}.git'
                print(f'\t- Cloning: {repo_name}')
                subprocess.run(['git', 'clone', clone_url], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                #For debugging
                #result = subprocess.run(['git', 'clone', clone_url], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                #stdout = result.stdout.decode('utf-8')
                #stderr = result.stderr.decode('utf-8')
                #print(stdout)
                #print(stderr)

elif args.command == 'aws':
    init(autoreset=True)
    if args.access_key and args.secret_key:
        #Enable this to verify useragent string is set to the below value if you don't believe me
        #boto3.set_stream_logger(name='botocore')
        user_agent_config = Config(user_agent='Boto3/1.9.89 Python/2.7.12 Linux/4.2.0-42-generic')
        
        aws_access_key = args.access_key
        aws_secret_access_key = args.secret_key
        aws_session_token = args.session

        try: 
            aws_client = boto3.client('sts',aws_access_key_id=aws_access_key, aws_secret_access_key=aws_secret_access_key, config = user_agent_config)
            response = aws_client.get_caller_identity()
            user_id = response['UserId']
            account_num = response['Account']
            arn = response['Arn']
            print('\n' + Fore.GREEN + '========================== Validating AWS Keys ==========================')
            print('User ID: ' + Fore.YELLOW + user_id)
            print('Account Number: ' + Fore.YELLOW + account_num)
            print('Account ARN: ' + Fore.YELLOW + arn)

        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'InvalidClientTokenId':
                print(Fore.RED + 'Keys are not valid')
            else:
                print(Fore.RED + 'Unknown error: ', e)

    if args.access_key and args.secret_key and args.session:
        #Enable this to verify useragent string is set to the below value if you don't believe me
        #boto3.set_stream_logger(name='botocore')
        user_agent_config = Config(user_agent='Boto3/1.9.89 Python/2.7.12 Linux/4.2.0-42-generic')
        
        try:
            aws_access_key = args.access_key
            aws_secret_access_key = args.secret_key
            aws_session_token = args.session

            aws_client = boto3.client('sts',aws_access_key_id=aws_access_key, aws_secret_access_key=aws_secret_access_key, aws_session_token=aws_session_token, config = user_agent_config)
            response = aws_client.get_caller_identity()
            print('\n' + Fore.GREEN + '========================== Validating AWS Keys ==========================')
            print('\n')
            print(response)
            print('\n')
            user_id = response['UserId']
            account_num = response['Account']
            arn = response['Arn']
            print('User ID: ' + Fore.YELLOW + user_id)
            print('Account Number: ' + Fore.YELLOW + account_num)
            print('Account ARN: ' + Fore.YELLOW + arn)
            

        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'InvalidClientTokenId':
                print(Fore.RED + 'Keys are not valid')
            else:
                print(Fore.RED + 'Unknown error: ', e)        

        if args.session_url:
            #Pulled from Amazon AWS documentation and edited to pass supplied tokens
            url_credentials = {}
            url_credentials['sessionId'] = args.access_key
            url_credentials['sessionKey'] = args.secret_key
            url_credentials['sessionToken'] = args.token
            json_string_with_temp_credentials = json.dumps(url_credentials)

            request_parameters = "?Action=getSigninToken"
            request_parameters += "&SessionDuration=43200"

            if sys.version_info[0] < 3:
                def quote_plus_function(s):
                    return urllib.quote_plus(s)
            else:
                def quote_plus_function(s):
                    return urllib.parse.quote_plus(s)
                
            request_parameters += "&Session=" + quote_plus_function(json_string_with_temp_credentials)
            request_url = "https://signin.aws.amazon.com/federation" + request_parameters
            r = requests.get(request_url)
            # Returns a JSON document with a single element named SigninToken.
            signin_token = json.loads(r.text)

            # Step 5: Create URL where users can use the sign-in token to sign in to 
            # the console. This URL must be used within 15 minutes after the
            # sign-in token was issued.
            request_parameters = "?Action=login" 
            request_parameters += "&Issuer=Example.org" 
            request_parameters += "&Destination=" + quote_plus_function("https://console.aws.amazon.com/")
            request_parameters += "&SigninToken=" + signin_token["SigninToken"]
            request_url = Fore.GREEN + "https://signin.aws.amazon.com/federation" + request_parameters

            # Send final URL to stdout
            print(request_url)

elif args.command == 'bitbucket':
    print('Full functionality hasn\'t been added into this script yet.')
    print('If you have a token you can use this command:')
    print('git clone --progress -v "https://{username}:{bitbucket-token}@bitbucketdomain.com/bb/{there may be some stuff here}')

          


            
