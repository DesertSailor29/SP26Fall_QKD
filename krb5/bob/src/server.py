import socket
import struct
import gssapi

HOST = "0.0.0.0"
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

credentials = gssapi.Credentials(
    name=service_name,
    usage="accept"
)

print(f"Bob is listening on {HOST}:{PORT}", flush=True)
print(f"Kerberos identity: {SERVICE_NAME}", flush=True)

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen(5)

while True:
    connection, address = server.accept()

    print(f"Connection from {address}", flush=True)

    context = gssapi.SecurityContext(
        creds=credentials,
        usage="accept"
    )

    try:
        token = recv_frame(connection)

        while not context.complete:
            output_token = context.step(token)

            if output_token:
                send_frame(connection, output_token)

            if not context.complete:
                token = recv_frame(connection)

        print("Kerberos authentication successful!", flush=True)
        print(f"Authenticated client: {context.initiator_name}", flush=True)

        send_frame(connection, b"Authentication successful!")

    except Exception as error:
        print(f"Authentication failed: {error}", flush=True)

    finally:
        connection.close()
