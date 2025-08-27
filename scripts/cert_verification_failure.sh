echo "Logging out of current user"
medperf auth logout
echo "Logging into testdo user for demo purposes"
medperf auth login -e testdo@example.com
echo "Obtaining certificate for testdo. Will overwrite existing cert. This is supposed to work."
medperf certificate get_client_certificate --ca-id 1 --overwrite
echo "Attempting to upload certificate to (local?) server. This should fail in certificate verification!"
medperf certificate submit --ca-id 1 --name UniqueName -y