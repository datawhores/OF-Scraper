This is a fork of onlyfans-scraper with additional features and fixes

# What should work
- scraping options like downloading content,unliking, and liking post

other options might not work currently.
If your auth is not correct, then the latest version will force a proper configuration

# Notes
This is a fork of onlyfans-scraper 
It has been optimized to make it more feature complete with dc's onlyfans script
A matter of fact with the right settings transitioning between the two scripts should be a easy enough process

In addition there are numerous filtering features to control exactly which type of content you want to scrape.
Though it is not complete check out the changes.md file for some general changes that have been made

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
pip install git+https://github.com/excludedBittern8/ofscraper.git 
```

If you're on macOS/Linux, then do this instead:
```
pip3 install ofscraper
```
or
```
pip3 install git+https://github.com/excludedBittern8/ofscraper.git 
```

## Authentication

You'll need to retrive your auth information 
https://github.com/excludedBittern8/ofscraper/wiki/Auth





## Usage

Whenever you want to run the program, all you need to do is type `ofscraper` in your terminal:

Basic usage is just to run the command below

```
ofscraper
```
You will be presented with 
menu options



For more advanced usage see
commandline args


# Issues
Open a issue in this repo, or you can mention your issue in the discord



# Migrating from DC script

You will need to change the settings so that the metadata option is compatible with your current folders
Additionally you might want to set the save_path, dir_path, and filename so they output similar outputs

The metadata path from dc's script is used for duplicate check so as long as your set the right path.
Files won't download a second time

https://github.com/excludedBittern8/ofscraper/wiki/Migrating-from-DC-script
https://github.com/excludedBittern8/ofscraper/wiki/Config Options
https://github.com/excludedBittern8/ofscraper/wiki/Customizing-save-path

Ask in the discord or open an issue if you need help with what to change to accomplish this



# Discord

https://discord.gg/zRXgb5Nv



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

