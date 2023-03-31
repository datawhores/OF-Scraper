This is a fork of onlyfans-scraper with additional features and fixes

Note the guide is still a little incomplete, so it might not be up to date with the changes I made 
I hope to go through it and make the necessary changes soon.

<h3>DISCLAIMERS:</h3>
<ol>
    <li>
        This tool is not affiliated, associated, or partnered with OnlyFans in any way. We are not authorized, endorsed, or sponsored by OnlyFans. All OnlyFans trademarks remain the property of Fenix International Limited.
    </li>
    <li>
        This is a theoritical program only and is for educational purposes. If you choose to use it then it may or may not work. You solely accept full responsability and indemnify the creator, hostors, contributors and all other involved persons from any any all responsability.
    </li>



  ## Description:
  command-line program to download media, and to process other batch operations such as liking and unliking posts.
    

![CopyQ nsUBdI](https://user-images.githubusercontent.com/67020411/227816586-fb685959-cd3f-45af-adea-14773b7154f9.png)




## Installation

### Recommended python3.9 or python3.10


Windows: 
```
pip install ofscraper
```
or 

```
pip install git+https://github.com/excludedBittern8/ofscraper
```

If you're on macOS/Linux, then do this instead:
```
pip3 install ofscraper
```
or
```
pip3 install git+https://github.com/excludedBittern/ofscraper
```

## Setup

Before you can fully use it, you need to fill out some fields in a `auth.json` file. This file will be created for you when you run the program for the first time.

These are the fields:

```json
{
    "auth": {
        "app-token": "",
        "sess": "",
        "auth_id": "",
        "auth_uniq_": "",
        "user_agent": "",
        "x-bc": ""
    }
}
```

It's really not that bad. I'll show you in the next sections how to get these bits of info.


### Step One: Creating the 'auth.json' File

You first need to run the program in order for the `auth.json` file to be created. To run it, simply type `ofscraper` in your terminal and hit enter. Because you don't have an `auth.json` file, the program will create one for you and then ask you to enter some information. Now we need to get that information.


### Step Two: Getting Your Auth Info

***If you've already used DIGITALCRIMINAL's OnlyFans script, you can simply copy and paste the auth information from there to here.***

Go to your [notification area](https://onlyfans.com/my/notifications) on OnlyFans. Once you're there, open your browser's developer tools. If you don't know how to do that, consult the following chart:

| Operating System | Keys |
| :----------------: | :----: |
| macOS | <kbd>alt</kbd><kbd>cmd</kbd><kbd>i</kbd> |
| Windows | <kbd>ctrl</kbd><kbd>shift</kbd><kbd>i</kbd> |
| Linux | <kbd>ctrl</kbd><kbd>shift</kbd><kbd>i</kbd> |

Once you have your browser's developer tools open, your screen should look like the following:

<img src="https://raw.githubusercontent.com/taux1c/onlyfans-scraper/main/media/browser_tools_open.png">

Click on the `Network` tab at the top of the browser tools:

<img src="https://raw.githubusercontent.com/taux1c/onlyfans-scraper/main/media/network_tab.png">

Then click on `XHR` sub-tab inside of the `Network` tab:

<img src="https://raw.githubusercontent.com/taux1c/onlyfans-scraper/main/media/xhr_tab.png">

Once you're inside of the `XHR` sub-tab, refresh the page while you have your browser's developer tools open. After the page reloads, you should see a section titled `init` appear:

<img src="https://raw.githubusercontent.com/taux1c/onlyfans-scraper/main/media/init.png">

When you click on `init`, you should see a large sidebar appear. Make sure you're in the `Headers` section:

<img src="https://raw.githubusercontent.com/taux1c/onlyfans-scraper/main/media/headers.png">

After that, scroll down until you see a subsection called `Request Headers`. You should then see three important fields inside of the `Request Headers` subsection: `Cookie`, `User-Agent`, and `x-bc`

<img src="https://raw.githubusercontent.com/taux1c/onlyfans-scraper/main/media/request_headers.png">

Inside of the `Cookie` field, you will see a couple of important bits:

* `sess=`
* `auth_id=`
* `auth_uid_=`

*Your* `auth_uid_` *will *only* appear **if you have 2FA (two-factor authentication) enabled**. Also, keep in mind that your* `auth_uid_` *will have numbers after the final underscore and before the equal sign (that's your auth_id).*

You need everything ***after*** the equal sign and everything ***before*** the semi-colon for all of those bits. 

Once you've copied the value for your `sess` cookie, go back to the program, paste it in, and hit enter. Now go back to your browser, copy the `auth_id` value, and paste it into the program and hit enter. Then go back to your browser, copy the `auth_uid_` value, and paste it into the program and hit enter (**leave this blank if you don't use 2FA!!!**).

Once you do that, the program will ask for your user agent. You should be able to find your user agent in a field called `User-Agent` below the `Cookie` field. Copy it and paste it into the program and hit enter.

After it asks for your user agent, it will ask for your `x-bc` token. You should also be able to find this in the `Request Headers` section.

You're all set and you can now use `ofscraper`.


## Usage

Whenever you want to run the program, all you need to do is type `ofscraper` in your terminal:

```
ofscraper
```

That's it. It's that simple.

 Once the program launches, all you need to do is follow the on-screen directions. The first time you run it, it will ask you to fill out your `auth.json` file (directions for that in the section above). 

You will need to use your arrow keys to select an option:

<img src="https://raw.githubusercontent.com/taux1c/onlyfans-scraper/main/media/main_menu.png" width="450">

If you choose to download content, you will have three options: having a list of all of your subscriptions printed, manually entering a username, or scraping *all* accounts that you're subscribed to.

<img src="https://raw.githubusercontent.com/taux1c/onlyfans-scraper/main/media/list_or_username.png" width="550">

### Liking/Unliking Posts

You can also use this program to like all of a user's posts or remove your likes from their posts. Just select either option during the main menu screen and enter their username.

This program will like posts at a rate of around one post per second. This may be reduced in the future but OnlyFans is strict about how quickly you can like posts.

At the moment, you can only like ~1000 posts per day. That's not *our* restriction, that's OnlyFans's restriction. So choose wisely.

### Migrating Databases

If you've used DIGITALCRIMINAL's script, you might've liked how his script prevented duplicates from being downloaded each time you ran it on a user. This is done through database files.

This program also uses a database file to prevent duplicates. In order to make it easier for user's to transition from his program to this one, this program will migrate the data from those databases for you (***only IDs and filenames***). 

In order to use it select the last option (Migrate an old database) and enter the *path* to the directory that contains the database files (*Posts.db, Archived.db, etc.*). 

For example, if you have a directory that looks like the following:

```
Users
|__ home
    |__ .sites
        |__ OnlyFans
            |__ melodyjai
                |__ Metadata
                    |__ Archived.db
                    |__ Messages.db
                    |__ Posts.db
```

Then the path you enter should be `/Users/home/.sites/OnlyFans/melodyjai/Metadata`. The program will detect the .db files in the directory and then ask you for the username to whom those .db files belong. The program will then move the relevant data over.

<h1> Bugs/Issues/Suggestions </h1>

If you run into trouble try the discord, careful though we do bite. If you open an issue for any of the following you will be banned from opening future issues. These are not issues they are operator error.

<ol>
    <li>
        Status Down - This means that your auth details are bad, keep trying.
    </li>
    <li>
        ofscraper command not found - This means that you have not added the path to your directory. You will have to look this up on your own with google.
    </li>
    <li>
        404 page not found or any other 404 error. - The post or profile can't be found. The user has been suspended or deleted or the post was removed and isn't completely deleted yet. No fix for this other than unsubscribing from the user. Do not open an issue for it.
    </li>
</ol>
<h3>Honestly unless you're one of my subscribers or support the project in some form your suggestions are generally ignored.</h3>

