from graphviz import Digraph

# Create a new directed graph
dot = Digraph(comment='CSV Scanner Architecture')
dot.attr(rankdir='TB')

# Set graph attributes
dot.attr('node', shape='box', style='filled', fillcolor='lightblue')
dot.attr('edge', color='#666666')

# Client Layer
with dot.subgraph(name='cluster_0') as c:
    c.attr(label='Client Layer')
    c.node('web', 'Web Browser')
    c.node('mobile', 'Mobile Browser')

# EC2 Instance
with dot.subgraph(name='cluster_1') as c:
    c.attr(label='EC2 Instance')
    
    # Application Layer
    with c.subgraph(name='cluster_2') as app:
        app.attr(label='Application Layer')
        app.node('nginx', 'Nginx\nReverse Proxy')
        app.node('gunicorn', 'Gunicorn\nWSGI Server')
        app.node('flask', 'Flask\nApplication')
    
    # Data Processing Layer
    with c.subgraph(name='cluster_3') as data:
        data.attr(label='Data Processing Layer')
        data.node('pandas', 'Pandas\nCSV Processor')
        data.node('bedrock', 'AWS Bedrock\nIntegration')
    
    # Storage Layer
    with c.subgraph(name='cluster_4') as storage:
        storage.attr(label='Storage Layer')
        storage.node('venv', 'Virtual\nEnvironment')
        storage.node('env', 'Environment\nVariables')

# AWS Services
with dot.subgraph(name='cluster_5') as c:
    c.attr(label='AWS Services')
    c.node('aws_bedrock', 'AWS Bedrock')
    c.node('s3', 'AWS S3')
    c.node('cloudwatch', 'CloudWatch')

# Add edges
dot.edge('web', 'nginx')
dot.edge('mobile', 'nginx')
dot.edge('nginx', 'gunicorn')
dot.edge('gunicorn', 'flask')
dot.edge('flask', 'pandas')
dot.edge('flask', 'bedrock')
dot.edge('bedrock', 'aws_bedrock')
dot.edge('pandas', 's3')
dot.edge('flask', 'venv')
dot.edge('flask', 'env')
dot.edge('aws_bedrock', 'cloudwatch')

# Save the diagram
dot.render('architecture', format='png', cleanup=True) 