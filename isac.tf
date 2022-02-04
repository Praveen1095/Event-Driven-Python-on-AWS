# configure aws as provider in terraform
provider "aws" {
  region = "us-east-1"
  access_key = "AKIA25RERQNIHDXAJLGI"
  secret_key = "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"
}

# using default vpc 
resource "aws_default_vpc" "default" {
  tags = {
    Name = "Default VPC"
  }
}

# configuring security group for db
resource "aws_security_group" "rds-sg" {
  name        = "db-secruity-group"
  description = "Allow TCP inbound traffic"
  vpc_id      = aws_default_vpc.default.id

  ingress {
    description      = "TCP from VPC"
    from_port        = 5432
    to_port          = 5432
    protocol         = "tcp"
    cidr_blocks      = ["0.0.0.0/0"]
  }

  egress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = ["0.0.0.0/0"]
  }

  tags = {
    Name = "db_instance"
  }
}

# setting up password policy for the database
resource "random_password" "password" {
  length           = 16
  special          = true
  override_special = "_%@"
}



# setting up postgre_db in aws not exceeding free tier limits
resource "aws_db_instance" "US_covid_db" {
  allocated_storage    = 10
  max_allocated_storage = 100
  storage_type = "gp2"
  engine               = "postgres"
  engine_version       = "12.3"
  instance_class       = "db.t2.micro"
  name                 = var.db_name
  username             = var.db_user
  password             = random_password.password.result
  vpc_security_group_ids = [aws_security_group.rds-sg.id]
  skip_final_snapshot  = true
  apply_immediately = true
  enabled_cloudwatch_logs_exports = [ "postgresql" ]
}

# ssm paramater store to hide the database username and password
resource "aws_ssm_parameter" "db_endpoint" {
  name        = "/database/US_covid_db/host"
  description = "The parameter to connect to the db"
  type        = "String"
  value       = aws_db_instance.US_covid_db.address
}

resource "aws_ssm_parameter" "db_user" {
  name        = "/database/US_covid_db/user"
  description = "name of the user db"
  type        = "String"
  value       = var.db_user
}

resource "aws_ssm_parameter" "db_password" {
  name        = "/database/US_covid_db/password"
  description = "password to connect to the db"
  type        = "String"
  value       = random_password.password.result
}

resource "aws_ssm_parameter" "db_name" {
  name        = "/database/US_covid_db/name"
  description = "name of the user db"
  type        = "String"
  value       = var.db_name
}

# vaiables saved seperatly and then referenced when needed

variable "db_name" {
  default = "us_covid_db"
  
}

variable "db_user" {
  default = "usa"
  
}