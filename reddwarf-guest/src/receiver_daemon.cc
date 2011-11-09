#include "nova/rpc/amqp.h"
#include "nova/guest/apt.h"
#include "nova/ConfigFile.h"
#include "nova/flags.h"
#include <boost/format.hpp>
#include "nova/guest/guest.h"
#include "nova/guest/GuestException.h"
#include <boost/lexical_cast.hpp>
#include "nova/guest/mysql.h"
#include "nova/guest/mysql/MySqlMessageHandler.h"
#include <boost/optional.hpp>
#include "nova/rpc/receiver.h"
#include "nova/rpc/sender.h"
#include <json/json.h>
#include "nova/Log.h"
#include <sstream>
#include <boost/thread.hpp>
#include "nova/guest/utils.h"

using nova::guest::apt::AptGuest;
using nova::guest::apt::AptMessageHandler;
using boost::format;
using boost::optional;
using namespace nova;
using namespace nova::flags;
using namespace nova::guest;
using namespace nova::guest::mysql;
using namespace nova::rpc;
using std::string;


const char PERIODIC_MESSAGE [] =
    "{"
    "    'method':'periodic_tasks',"
    "    'args':{}"
    "}";

static bool quit;

/* This runs in a different thread and just sends messages to the queue,
 * which cause the periodic_tasks to run. This keeps us from having to ensure
 * everything else is thread-safe. */
class PeriodicTasker {

private:
    string guest_ethernet_device;
    Log log;
    JsonObject message;
    MySqlConnectionPtr nova_db;
    string nova_db_name;
    Sender sender;

public:
    PeriodicTasker(AmqpConnectionPtr connection, const char * topic,
                   MySqlConnectionPtr nova_db, string nova_db_name,
                   string guest_ethernet_device)
      : guest_ethernet_device(guest_ethernet_device),
        log(),
        message(PERIODIC_MESSAGE),
        nova_db(nova_db),
        nova_db_name(nova_db_name),
        sender(connection, topic)
    {
    }

    void loop(unsigned long periodic_interval) {
        while(!quit) {
            log.info2("Waiting for %lu seconds to run periodic tasks...",
                      periodic_interval);
            boost::posix_time::seconds time(periodic_interval);
            boost::this_thread::sleep(time);

            log.info("Running periodic tasks...");
            MySqlNovaUpdaterPtr updater = sql_updater();
            MySqlNovaUpdater::Status status = updater->get_local_db_status();
            updater->update_status(status);
        }
    }

    MySqlNovaUpdaterPtr sql_updater() const {
        // Ensure a fresh connection.
        nova_db->close();
        nova_db->init();
        // Begin using the nova database.
        string using_stmt = str(format("use %s")
            % nova_db->escape_string(nova_db_name.c_str()));
        nova_db->query(using_stmt.c_str());
        MySqlNovaUpdaterPtr ptr(new MySqlNovaUpdater(
            nova_db, guest_ethernet_device.c_str()));
        return ptr;
    }
};


int main(int argc, char* argv[]) {
    quit = false;
    Log log;

#ifndef _DEBUG

    try {
        daemon(1,0);
#endif

        /* Grab flag values. */
        FlagValues flags(FlagMap::create_from_args(argc, argv, true));

        /* Create connection to Nova database. */
        MySqlConnectionPtr nova_db(new MySqlConnection(
            flags.nova_sql_host(), flags.nova_sql_user(),
            flags.nova_sql_password()));

        /* Create JSON message handlers. */
        const int handler_count = 2;
        MessageHandlerPtr handlers[handler_count];

        /* Create Apt Guest */
        AptGuest apt_worker(flags.apt_use_sudo());
        handlers[0].reset(new AptMessageHandler(&apt_worker));

        /* Create MySQL Guest. */
        MySqlMessageHandlerConfig mysql_config;
        mysql_config.apt = &apt_worker;
        mysql_config.guest_ethernet_device = flags.guest_ethernet_device();
        mysql_config.nova_db_host = flags.nova_sql_host();
        mysql_config.nova_db_name = flags.nova_sql_database();
        mysql_config.nova_db_password = flags.nova_sql_password();
        mysql_config.nova_db_user = flags.nova_sql_user();
        handlers[1].reset(new MySqlMessageHandler(mysql_config));


        /* Create AMQP connection. */
        string topic = "guest.";
        topic += nova::guest::utils::get_host_name();

        AmqpConnectionPtr connection = AmqpConnection::create(
            flags.rabbit_host(), flags.rabbit_port(), flags.rabbit_userid(),
            flags.rabbit_password(), flags.rabbit_client_memory());

        /* Create receiver. */
        Receiver receiver(connection, topic.c_str());

        /* Create tasker. */
       PeriodicTasker tasker(connection, topic.c_str(),
                             nova_db, flags.nova_sql_database(),
                             flags.guest_ethernet_device());

        quit = false;

        boost::thread workerThread(&PeriodicTasker::loop, &tasker,
                                   flags.periodic_interval());

        while(!quit) {
            log.info("Waiting for next message...");
            GuestInput input = receiver.next_message();
            GuestOutput output;

            log.info2("method=%s", input.method_name.c_str());
            log.info2("args=%s", input.args->to_string());

            #ifndef _DEBUG
            try {

                if (input.method_name == "exit") {
                    quit = true;
                }
            #endif
                JsonDataPtr result;
                for (int i = 0; i < handler_count && !result; i ++) {
                    output.result = handlers[i]->handle_message(input);
                }
                if (!output.result) {
                    throw GuestException(GuestException::NO_SUCH_METHOD);
                }
                output.failure = boost::none;
            #ifndef _DEBUG
            } catch(const std::exception & e) {
                log.error2("Error running method %s : %s",
                           input.method_name.c_str(), e.what());
                log.error(e.what());
                output.result.reset();
                output.failure = e.what();
            }
            #endif
            receiver.finish_message(output);
        }
#ifndef _DEBUG
    } catch (const std::exception & e) {
        log.error2("Error: %s", e.what());
    }
#endif
    return 0;
}
