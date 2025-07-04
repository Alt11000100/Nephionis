from jinja2 import Environment, FileSystemLoader
import os

def scrape_interval(seconds="5"):
    '''Function for the scrape interval of prometheus'''
    # Load the directory where the template is
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("prometheus.yml.j2")

    scrape = seconds + "s"
    # Render with your chosen interval
    rendered = template.render(scrape_interval=scrape)

    # Save it to file
    with open("prometheus.yml", "w") as f:
        f.write(rendered)

def create_dockerfile(version='latest',dockerfile_name='Dockerfile',folder_to_run="binary",user_emul=True):
    '''Use a jinja2 template to create a dockerfile'''

    env = Environment(loader=FileSystemLoader("templates"))
    # Use the jinja tamplate
    template = env.get_template('Dockerfile-malw.j2')
    # Produce output
    output = template.render(
            version = version,
            folder_to_run = folder_to_run,
            user_emul = user_emul
        )
    
    dockerfile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), dockerfile_name)
    
    with open(dockerfile_path, 'w') as f:
            f.write(output)

    return dockerfile_path

#  Test

# scrape_interval()

# print(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dockerfile_name'))

# create_dockerfile()