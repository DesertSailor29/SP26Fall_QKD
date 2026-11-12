import socket
import struct
import gssapi

SERVER = "bob"
PORT = 5000
SERVICE_NAME = "bob/localhost@PROJECT.TEST"


def recv_exact(connection, size):
    data = b""

    while len(data) < size:
        chunk = connection.recv(size - len(data))

        if not chunk:
            raise ConnectionError("Connection closed unexpectedly")

        data += chunk

    return data


def send_frame(connection, data):
    connection.sendall(struct.pack("!I", len(data)) + data)


def recv_frame(connection):
    length = struct.unpack("!I", recv_exact(connection, 4))[0]

    if length > 1_000_000:
        raise ValueError("Token is too large")

    return recv_exact(connection, length)


service_name = gssapi.Name(
    SERVICE_NAME,
    name_type=gssapi.NameType.kerberos_principal
)

context = gssapi.SecurityContext(
    name=service_name,
    usage="initiate",
    flags=[gssapi.RequirementFlag.mutual_authentication]
)

print("Connecting to Bob...")

with socket.create_connection((SERVER, PORT)) as connection:

    token = context.step()

    if token:
        send_frame(connection, token)

    while not context.complete:
        server_token = recv_frame(connection)
        token = context.step(server_token)

        if token:
            send_frame(connection, token)

    print("Kerberos authentication successful!")
    print(f"Authenticated server: {context.target_name}")

    response = recv_frame(connection)
    print("Bob says:", response.decode())
