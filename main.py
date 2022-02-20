import socket
import binascii  # for crc
import threading
import math
import random
from collections import deque
import time


class fragment:
    def __init__(self, flag_num, num_of_frags, id_of_frag, checksum, dataa):
        self.data = bytearray()
        self.data.extend(flag_num.to_bytes(1, "big"))
        if num_of_frags is not None:
            self.data.extend(num_of_frags.to_bytes(4, "big"))
        if id_of_frag is not None:
            if id_of_frag > 65535:
                id_of_frag %= 65535
            self.data.extend(id_of_frag.to_bytes(2, "big"))
        if checksum is not None:
            self.data.extend(checksum.to_bytes(2, "big"))
        if dataa is not None:
            self.data.extend(bytearray(dataa))

    def change_data(self):
        if int.from_bytes(self.data[9:10], "big") < 200:
            self.data[9] += 1
        else:
            self.data[9] -= 1

    def get_length(self):  # returns length of fragment without header
        return len(self.data) - 9


class fragment_rec:
    def __init__(self, dataa):
        self.data = bytearray()
        self.data.extend(dataa)

    def get_length(self):  # returns length of fragment without header
        return len(self.data) - 9

    def get_flag(self):
        return int.from_bytes(self.data[0:1], "big")

    def get_num_of_frags(self):
        return int.from_bytes(self.data[1:5], "big")

    def get_id_of_frag(self):
        return int.from_bytes(self.data[5:7], "big")

    def get_checksum(self):
        return int.from_bytes(self.data[7:9], "big")

    def compute_checksum(self):
        return binascii.crc_hqx(self.data[9:len(self.data)], 0)

    def get_data(self):
        return self.data[9:len(self.data)]


def send_start_fragment(ip_add, port, soc):
    start_fragment = fragment(128, None, None, None, None)
    counter = 0

    while counter != 3:
        soc.settimeout(None)
        soc.sendto(start_fragment.data, (ip_add, port))
        soc.settimeout(3)
        try:
            data, add_port = soc.recvfrom(1024)
            response = fragment_rec(data)

            if response.get_flag() == 4:
                print(f"Spojenie s serverom {add_port} prebehlo uspesne!")
                return 0
        except (ConnectionResetError, socket.timeout):
            print("Od servera som nedostal potvrdenie spojenia.")
            counter += 1
            time.sleep(3)
        if counter == 3:
            print("3 krat som nedostal potvrdenie spojenia. vypinam sa..")

            soc.close()
            return 1



def create_next_message_fragment(message, start_pos, fragment_size):
    fragment_mess = bytearray()
    end_position = int()
    if start_pos + fragment_size >= len(message):
        fragment_mess = message[start_pos:len(message)]
        end_position = len(message)
    else:
        fragment_mess = message[start_pos:start_pos + fragment_size]
        end_position = start_pos + fragment_size
    return fragment_mess, end_position


def send_ka_message(ip_add, port, soc):
    ka_frag = fragment(8, None, None, None, None)
    soc.sendto(ka_frag.data, (ip_add, port))


def send_fin_message(ip_add, port, soc):
    fin_frag = fragment(64, None, None, None, None)
    soc.sendto(fin_frag.data, (ip_add, port))


def ka_func(active, ip_port, sockt):
    i = 0
    while not active.isSet():
        e2 = active.wait(5)
        if not e2:
            send_ka_message(ip_port[0], ip_port[1], sockt)
            sockt.settimeout(1)
            try:
                data, app_port = sockt.recvfrom(2048)
            except (socket.timeout, ConnectionResetError):
                sockt.settimeout(None)
                i += 1
                if i == 3:
                    print(
                        "\nServer neodpovedal 3 krat na Keep alive spravu.. Posielam spravu o ukonceni a vypinam sa..\n Pre pokracovanie stlac enter")
                    send_fin_message(ip_port[0], ip_port[1], sockt)
                    sockt.close()
                    active.set()
                continue
            received = fragment_rec(data)
            if received.get_flag() != 12:
                i += 1
            if i == 3:
                print(
                    "\nServer neodpovedal 3 krat na Keep alive spravu.. Posielam spravu o ukonceni a vypinam sa..\n Pre pokracovanie stlac enter")
                send_fin_message(ip_port[0], ip_port[1], sockt)
                sockt.close()
                active.set()


def create_queque_of_file_data(filename, fragment_size):
    filename.replace('\\\\', '\\')
    f = open(filename, "rb")
    q = deque()
    readed = f.read(fragment_size)
    q.append(readed)
    while readed:
        readed = f.read(fragment_size)
        if readed == b'':
            break
        q.append(readed)

    f.close()
    return q


def get_name(filename):
    name = list()
    str_e = str()

    for i in range(len(filename) - 1, 0, -1):
        if filename[i] == "\\":
            break
        else:
            name.append(filename[i])
    name.reverse()
    return str_e.join(name)


def client():
    print('klient!')
    print('Zadaj ip adresu:', end=" ")
    ip_add = input()
    print('Zadaj port:', end=" ")
    port = int(input())
    client_soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # creating client socket

    print('Zadaj maximalnu velkost fragmentu (1 - 1465 B)')
    max_size = int(input())
    while max_size <= 0 or max_size > 1465:
        print('Zadaj velkost fragmentu znova: ')
        max_size = int(input())
    if send_start_fragment(ip_add, port, client_soc) == 1:
        return 0

    while 1:
        active = threading.Event()
        ka_thread = threading.Thread(target=ka_func, daemon=True, args=(active, (ip_add, port), client_soc))
        print('Typy sprav')
        print('\t\tM - poslanie spravy')
        print('\t\tF - poslanie suboru')
        print('\t\tK - ukoncenie spojenia')
        ka_thread.start()
        active.clear()
        frr = 0
        while 1:
            if frr:
                break

            print('Zadaj typ spravy: ', end=" ")
            type_input = input()

            if active.is_set():
                ka_thread.join()
                return 0

            if type_input == 'M':
                print('Zadaj spravu na poslanie: ', end=" ")
                message = input()
                if active.is_set():
                    ka_thread.join()
                    return 0
                message_in_bytes = message.encode()
                active.set()
                ka_thread.join()

                timeout_counter = 0
                start_pos = 0
                counter = 0
                count_of_fragments = math.ceil(len(message) / max_size)
                last_sended = 0
                while start_pos != len(message_in_bytes):
                    mess_frag, end_pos = create_next_message_fragment(message_in_bytes, start_pos, max_size)
                    send_mess = fragment(32, count_of_fragments, counter + 1, binascii.crc_hqx(mess_frag, 0), mess_frag)
                    size_of_frag = send_mess.get_length()
                    if random.random() < 0.2:  # 20 % that will be send bad data
                        send_mess.change_data()
                    client_soc.sendto(send_mess.data, (ip_add, port))
                    client_soc.settimeout(1)
                    try:
                        data, app_port = client_soc.recvfrom(2048)
                    except socket.timeout:
                        print("Nedostal som odpoved 1 sekundu po odoslani.. Posielam znova..")
                        client_soc.settimeout(None)

                        if last_sended == counter + 1:
                            timeout_counter += 1
                        else:
                            timeout_counter = 0
                        if timeout_counter == 2:
                            send_fin_message(ip_add, port, client_soc)
                            print("Timeout 3 krat za sebou.. Posielam fin spravu a vypinam sa..")
                            client_soc.close()
                            return 0
                        last_sended = counter + 1
                        continue
                    except ConnectionResetError:

                        print("Server bol odpojeny..")
                        client_soc.settimeout(None)
                        client_soc.close()
                        return 0
                    client_soc.settimeout(None)
                    received = fragment_rec(data)
                    if received.get_flag() == 4:
                        print(
                            f"Fragment s cislom {received.get_id_of_frag()} s velkostou {size_of_frag} bol uspesne poslany")
                        counter += 1

                        start_pos = end_pos
                    elif received.get_flag() == 2:
                        print(
                            f"Fragment s cislom {received.get_id_of_frag()} s velkostou {size_of_frag} bol chybne poslany.. posielam znova")
                    if start_pos == len(message_in_bytes):
                        print(f"Pocet odoslanych fragmentov {counter}")

                        break
                frr = 1

                data = None
                change_server = fragment(1, None, None, None, None)
                client_soc.sendto(change_server.data, (ip_add, port))
                client_soc.settimeout(4)
                try:
                    data, app_port = client_soc.recvfrom(2048)
                except socket.timeout:
                    print("Nedostal som odpoved pre zmenu.")
                    continue
                rec = fragment_rec(data)
                if rec.get_flag() == 1:
                    print("Server chce zmenit ulohy.. ")
                    return 1

            elif type_input == 'F':
                timeout_counter = 0
                print('Zadaj cestu k suboru ,kt. sa ide poslat: ', end=" ")
                filename = input()
                if active.is_set():
                    ka_thread.join()
                    return 0
                active.set()
                ka_thread.join()

                name_of_file = get_name(filename)
                name_of_file = name_of_file.encode()
                flag = 0
                exc = 0
                while flag != 4:
                    send_mess = fragment(144, 0, 0, binascii.crc_hqx(name_of_file, 0), name_of_file)

                    client_soc.sendto(send_mess.data, (ip_add, port))
                    client_soc.settimeout(60)
                    try:
                        data, app_port = client_soc.recvfrom(2048)
                    except socket.timeout:
                        print("Nedostal som odpoved 60 s..")
                        client_soc.settimeout(None)
                        send_fin_message(ip_add, port, client_soc)
                        client_soc.close()
                        frr = 1
                        exc = 1
                        return 0
                    except ConnectionResetError:

                        print("Server bol odpojeny..")
                        client_soc.settimeout(None)
                        client_soc.close()
                        return 0
                    client_soc.settimeout(None)
                    received = fragment_rec(data)
                    flag = received.get_flag()
                if exc == 1:
                    break

                qu = create_queque_of_file_data(filename, max_size)
                timeout_counter = 0
                counter = 0
                count_of_fragments = len(qu)
                last_sended = 0
                while len(qu) > 0:
                    fragment_data = qu[0]
                    send_data = fragment(16, count_of_fragments, counter + 1, binascii.crc_hqx(fragment_data, 0),
                                         fragment_data)
                    size_of_frag = send_data.get_length()
                    if random.random() < 0.2:  # 20 % that will be send bad data
                        send_data.change_data()
                    client_soc.sendto(send_data.data, (ip_add, port))
                    client_soc.settimeout(1)
                    try:
                        data, app_port = client_soc.recvfrom(2048)
                    except socket.timeout:
                        print("Nedostal som odpoved 1 sekundu po odoslani.. Posielam znova..")
                        client_soc.settimeout(None)

                        if last_sended == counter + 1:
                            timeout_counter += 1
                        else:
                            timeout_counter = 0
                        if timeout_counter == 2:
                            send_fin_message(ip_add, port, client_soc)
                            print("Timeout 3 krat za sebou.. Posielam fin spravu a vypinam sa..")
                            client_soc.close()
                            return 0
                        last_sended = counter + 1
                        continue
                    except ConnectionResetError:

                        print("Server bol odpojeny..")
                        client_soc.settimeout(None)
                        client_soc.close()
                        return 0
                    client_soc.settimeout(None)
                    received = fragment_rec(data)
                    if received.get_flag() == 4:
                        print(
                            f"Fragment s cislom {received.get_id_of_frag()} s velkostou {size_of_frag} bol uspesne poslany")
                        qu.popleft()
                        counter += 1
                        if len(qu) == 0:
                            frr = 1
                            print(f"Pocet spravne odoslanych fragmentov: {counter}")
                            print(f"absolutna cesta k suboru: {filename}")
                            change_server = fragment(1, None, None, None, None)
                            client_soc.sendto(change_server.data, (ip_add, port))
                            client_soc.settimeout(4)
                            try:
                                data, app_port = client_soc.recvfrom(2048)
                            except socket.timeout:
                                print("Nedostal som odpoved pre zmenu.")
                            rec = fragment_rec(data)
                            if rec.get_flag() == 1:
                                print("Zmena od servera..")
                                return 1

                    elif received.get_flag() == 2:
                        print(
                            f"Fragment s cislom {received.get_id_of_frag()} s velkostou {size_of_frag} bol chybne poslany.. posielam znova")

            elif type_input == 'K':
                active.set()
                send_fin_message(ip_add, port, client_soc)
                if ka_thread.is_alive():
                    ka_thread.join()
                client_soc.close()
                return 0


def send_reply_message(add_port, soc, flag, number_of_fragments, id_number):
    flag_fragment = fragment(flag, number_of_fragments, id_number, None, None)
    soc.sendto(flag_fragment.data, add_port)


def server():
    print('server!')
    print('Zadaj port na, kt. mam pocuvat:', end=" ")
    port = int(input())
    serv_soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # creating client socket
    serv_soc.bind(('', port))
    serv_soc.settimeout(60)

    mess = str()
    name_of_file = str()
    path = str()
    f = None
    counter = 0
    tofile = bytearray()
    while 1:
        data = bytearray()
        add_port = tuple()

        try:
            data, add_port = serv_soc.recvfrom(2048)
        except socket.timeout:
            print("Server nedostal ziadne data 60 sekund, preto sa vypina")
            serv_soc.close()
            break

        received = fragment_rec(data)
        if received.get_flag() == 128:
            print(f"Pokusa sa pripojit {add_port}.. posielam potvrdenie...")

            send_reply_message(add_port, serv_soc, 4, None, None)

        elif received.get_flag() == 32:
            if received.get_checksum() != received.compute_checksum():
                send_reply_message(add_port, serv_soc, 2, received.get_num_of_frags(), received.get_id_of_frag())
                print(f"fragment cislo {received.get_id_of_frag()} dlzky {received.get_length()} je chybny")
            else:
                counter += 1
                print(f"fragment cislo {received.get_id_of_frag()} dlzky {received.get_length()} bol prijaty")
                send_reply_message(add_port, serv_soc, 4, received.get_num_of_frags(), received.get_id_of_frag())
                mess += (received.get_data()).decode()
                if counter == received.get_num_of_frags():
                    print(f"Prijata sprava: {mess}\n")
                    print(f"Pocet spravne prijatych fragmentov: {counter}\n")
                    counter = 0
                    mess = str()
        elif received.get_flag() == 1:
            print("AK sa chces zmenit na klienta klikni ctrl+c do 3 sekund")
            try:
                time.sleep(3)
            except KeyboardInterrupt:
                change_fragment = fragment(1, None, None, None, None)
                serv_soc.sendto(change_fragment.data, add_port)
                return 1
            print("Nestihol si pokracujeme...")
        elif received.get_flag() == 8:
            send_reply_message(add_port, serv_soc, 12, 0, 0)
        elif received.get_flag() == 144:
            if received.get_checksum() != received.compute_checksum():
                send_reply_message(add_port, serv_soc, 2, received.get_num_of_frags(), received.get_id_of_frag())
            else:
                name_of_file = received.get_data().decode()
                path = input("zadaj cestu kde ma byt subor ulozeny: ")
                send_reply_message(add_port, serv_soc, 4, received.get_num_of_frags(), received.get_id_of_frag())


        elif received.get_flag() == 16:
            if received.get_checksum() != received.compute_checksum():
                send_reply_message(add_port, serv_soc, 2, received.get_num_of_frags(), received.get_id_of_frag())
                print(f"fragment cislo {received.get_id_of_frag()} dlzky {received.get_length()} je chybny")

            else:
                counter += 1
                print(f"fragment cislo {received.get_id_of_frag()} dlzky {received.get_length()} bol prijaty")
                send_reply_message(add_port, serv_soc, 4, received.get_num_of_frags(), received.get_id_of_frag())
                tofile.extend(received.get_data())
                if counter == received.get_num_of_frags():
                    f = open(path + '\\' + name_of_file, "wb")
                    path = path + '\\' + name_of_file
                    f.write(tofile)
                    print(f"Prijaty subor: {path}")
                    print(f"Pocet spravne prijatych fragmentov: {counter}\n")
                    tofile = bytearray()
                    path = str()
                    name_of_file = str()
                    counter = 0
                    f.close()
        elif received.get_flag() == 64:
            print("prisla poziadavka o ukoncenie spojenia.. koncim..")
            serv_soc.close()
            return 0

    return 0


def main():
    print('Prikazy \n\t\t0 - klient\n\t\t1 - server\n\t\t2 - koniec programu\n')
    print('Zadaj prikaz:', end=" ")
    comm = input()
    c = None
    x = None
    while comm != '2':
        if comm == '0':

            c = client()
        elif comm == '1':
            x = server()

        print('Prikazy \n\t\t0 - klient\n\t\t1 - server\n\t\t2 - koniec programu\n')
        print('Zadaj prikaz:', end=" ")
        if c == 1:
            comm = '1'
            c = 0
            continue
        if x == 1:
            comm = '0'
            x = 0
            continue
        comm = input()


if __name__ == '__main__':
    main()
