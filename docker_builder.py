import docker
import os


base_dir = os.path.dirname(__file__) # The root of your project
dockerfile_path = os.path.join(base_dir, 'templates', 'Dockerfile')
context_path = base_dir  

class Builder:

    def __init__(self,build_arguments=None,dockerfile=dockerfile_path):
        self.dockerfile = dockerfile
        self.client = docker.from_env()




    def build_image(self,tag,buildargs):
        ''' Build an image from a dockerfile'''

        # we can specify malware from builder args maybe?
        image, build_logs = self.client.images.build(
            dockerfile=self.dockerfile,
            forcerm=False,
            buildargs=buildargs,
            # network_mode=None, # check if this helps
            quiet=False,
            tag=f"builder_test:{tag}",
            path=context_path
        )

        for chunk in build_logs:
            if 'stream' in chunk:
             print(chunk['stream'].strip())

        

        return image

    def remove_image(self,image,force=True):
        """
        Remove a Docker image using the Docker client.

        Args:
            image (docker.models.images.Image): The Docker image to be removed.
        """

        self.client.images.remove(image.id, force=force)

# Test

# print(dockerfile_path)

# Instance().build_image()

# Builder().remove_image("6c1af2e6ef6b4cfca1aeeeeaf247daed")