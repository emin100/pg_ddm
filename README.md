# INSTALLATION
 
## OVER Docker
    
    docker run -d -p 15432:15432 -p 25432:25432 -p 35432:5432 -p 42379:2379 --name pg_test emin100/pg_ddm
 
  
 
 
 | Type | Use this port in docker conteiner  | Use this port out docker container  |
 | ------- | :---: | :---: |
 | pg_ddm connection port as the same as pgbouncer | 15432 | 15432 |
 | pg_ddm UI port. Connect http://localhost:25432. Default username and password is admin | 25432 | 25432 |
 | postgresql instance port. You can direct accses postgresql. Default username, password and dbname is docker.  | 5432 | 35432 |
 | etcd port | 2379 | 42379 |
 

 
 Thats All!
 
## OVER Source Code
 
###### Download source codes
 
    git clone https://github.com/emin100/pg_ddm.git --recursive
    cd pg_ddm
    
###### Install dependency
 
    sudo apt install make etcd virtualenv libevent-dev pkg-config openssl libtool m4 autotools-dev automake libssl-dev ruby ruby-dev
    
###### Install pandoc for pgbouncer doc

    wget https://github.com/jgm/pandoc/releases/download/2.7.2/pandoc-2.7.2-1-amd64.deb
    sudo dpkg -i  pandoc-2.7.2-1-amd64.deb 
    rm -rf pandoc-2.7.2-1-amd64.deb 

###### Download Pgbouncer source code and patch it

    cp -R pgbouncer_diff/* pgbouncer/
    cd pgbouncer
    git apply pg_ddm.patch
    
    
    ./autogen.sh
    ./configure
    make
    
###### Install Ruby Things
 
    cd ../pg_query
    gem build pg_query.gemspec 
    sudo gem install pg_query-*.gem
    sudo gem install hashie etcdv3
    
    
###### Install UI Things
    
    cd ..
    virtualenv --python=python3 venv
    source venv/bin/activate
    cd admin
    pip install -r requirements.txt
