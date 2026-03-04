# escape=`

# Windows container base
FROM mcr.microsoft.com/windows/servercore:ltsc2022

SHELL ["cmd", "/S", "/C"]

# ---- Install Python (official embeddable ZIP) ----
# Pick a version you want; 3.11 works well with pythonnet.
ENV PY_VER=3.11.8
ENV PY_ZIP=python-%PY_VER%-embed-amd64.zip
ENV PY_URL=https://www.python.org/ftp/python/%PY_VER%/%PY_ZIP%
ENV PY_HOME=C:\Python
ENV PATH=C:\Python;C:\Python\Scripts;%PATH%

ADD %PY_URL% C:\temp\python.zip
RUN mkdir %PY_HOME% && `
    powershell -NoProfile -Command "Expand-Archive -Path C:\temp\python.zip -DestinationPath $env:PY_HOME" && `
    del C:\temp\python.zip

# Enable site-packages + pip in embeddable python
RUN powershell -NoProfile -Command ^
    "$pth = Get-ChildItem $env:PY_HOME -Filter 'python*.pth' | Select-Object -First 1; " ^
    "(Get-Content $pth.FullName) -replace '#import site','import site' | Set-Content $pth.FullName"

# Install pip
ADD https://bootstrap.pypa.io/get-pip.py C:\temp\get-pip.py
RUN python C:\temp\get-pip.py && del C:\temp\get-pip.py

# ---- Python deps ----
RUN pip install --no-cache-dir pythonnet==3.0.3 pyserial

# ---- Kinesis DLL location ----
# Recommended: mount Kinesis installation directory from host into this path at runtime.
# Example mount:
#   -v "C:\Program Files\Thorlabs\Kinesis:C:\Kinesis:ro"
ENV KINESIS_DIR=C:\Kinesis

# Copy your app
WORKDIR C:\app
COPY . C:\app

# Default command
CMD ["python", "main.py"]