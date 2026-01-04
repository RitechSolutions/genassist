terraform init
TF_LOG=debug GODEBUG=asyncpreemptoff=1 terraform plan 
TF_LOG=debug GODEBUG=asyncpreemptoff=1 terraform apply