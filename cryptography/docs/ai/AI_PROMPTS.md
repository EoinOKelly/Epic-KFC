# AI Prompts (Epic Messaging, CS4455)

Main prompts I used with Cursor while working on crypto, blockchain, and getting the backend running on the VM. Skipped the useless ones (commit messages, empty messages, etc.).

---

## 1. Cryptography

### Initial module

> I need to build the standalone Cryptography module for our secure messaging app. This needs to be a set of utility functions my teammates can import into their clients/backend.
>
> Please create a TypeScript/Node.js module (e.g., `cryptoEngine.ts`) that implements the following functions using standard, vetted libraries (like 'libsodium-wrappers' or Node's native 'crypto'):
>
> 1. `hashPassword(password)`: Hashes a password using Argon2id. Return the hash and salt.
> 2. `deriveKeys(masterKey, salt)`: Uses HKDF to derive multiple sub-keys (e.g., one for local storage encryption, one for session).
> 3. `encryptMessage(plaintext, symmetricKey)`: Encrypts a message using AES-256-GCM. Must include an authentication tag and Initialization Vector (IV).
> 4. `decryptMessage(ciphertext, iv, authTag, symmetricKey)`: Decrypts the AEAD message.
> 5. `generateKeyPair()`: Generates an asymmetric keypair suitable for HPKE/TOFU.
> 6. `encryptPrivateKeyForStorage(privateKey, storageKey)`: Encrypts the user's private key at rest.
>
> Add extensive inline comments explaining the parameters chosen (especially the Argon2id memory limits and the AEAD choice) so I can justify them in my cryptographic design document.

### Signal / brief

> I want to use the signal protocol because I believe that is standard, the encrypition should be a form of quantam secure AES-256-GCM i believe @CS4455-Epic-2026 (1).pdf
>
> https://en.wikipedia.org/wiki/Signal_Protocol u should essentialy do the encryption like they do here, do they use AES-256-GCM

### Cleanup / understanding

> explain every file you have and what they do, remove any unecesary lines of code or comments, dont make this look like AI slop
>
> what is the x in x3dh and what is the double ratchet?

### Rolling own crypto / lecturer stuff

> is the cryptography stuff overcomplicated, in any situation am I just rolling my own crypto when I should instead just be calling a specific function or something?
>
> anything that is bad practice, fix, I want to be able to clearly justify everything without any mistakes, also let me know what I need to store in the db for my teamate
>
> are there any red flags or issues in any of my cryptography that my lecturer could grill me on, im thinking lacking quantam security, rolling my own crypto, why i chose specific method, any possible issues, also explain to me how this will hook up to the other parts of this project and how and where it slots in

### Docs

> feel free to add a general documentation or wiki folder to the project to inc;ude anyhting fitting such as diagrams

### libsignal / libraries

> in general for this project i would say if there is a standard library, use that standard library
>
> Better alignment with your rule: use @signalapp/libsignal-client (or a maintained TS port) for session setup and ratcheting, and keep your package for:
> Argon2 / HKDF / at-rest GCM
> Wire format + DB types
> TOFU helpers do this then
>
> why is this better than what u have before, is there any reason I shouldnt have changed this, does this have any postive or negative conetations or changes for the project as a whole?

### GCM vs brief

> what is the best way of doing the crypto so, as far as I know, you should always use a library rather than rolling anything yourself also i noticed that you changed to cbc + hmac, does the brief not explicitly say to do GCM rather than nay encrypt than mac sheme, do not go against the brief, fix anything where you go against it

### Backend integration

> okay break down the full flow of everything here now so, and then give me a git commit message, also if i pull from main will it override the changes i have made to files locally here?
>
> okay i just pulled the full server backend, our next task is to somehow combine all of my code and the backend code together to actually get this working, lets takt this slow and make sure that each thing is working before doing the next it is esential that I understand this
>
> when i run smoke signal what is actually happening, could we have some log outputs or something aswell to tell me cnrypted decrypted ect is my cryptography high standard and industry grade or are there issues, if it is industry grade I am happy to start working away on making changes to the code, it would also be handy if I could actually test these changes myself so like I can see messages sending and being encrypted and all but im not sure if that exists in the code
>
> make everythin fully post quantam proof, i thinkk usually doubling the bit range ight fix this but idk if this is how it works for X25519 tbh idek what that is to begin with, hould TOFU be handled in my code or is that also in the server backend code?
>
> ignore last 2 git prompts, i have a teamate working on client, for now help me set up that the cryptography i have built is used and called at the right times and places in the backend and that it all works perfectly together, dont make a million changes at once as i want to review them
>
> so explain this a little further, what was the purpose of this before vs the purpose of this now?
>
> okay lets move on to the next step now, eventually will the backend be running my TS crypto?
>
> so I am doing the crypto part what ways does it link with teamate 1s backend and what way will it link with teamate 2s future client? was TS the right choice to write my crypto in? also feel free to make nay minor essential changes to backend that are needed other than that let me know if I am done putting everything together for the time being and if I am let me know what I can see myself to ensure it is all working the right way together
>
> so what is the purpose of my code, just a cross reference for the same code in the py backend? my teamate was asking if i looked at his endpoints for the keys, what is meant by this? Also are we no longer using double ratchet or do we still use it?
>
> is the client not seperate entirley in c++, is any of my TS code currently being ran or how will this work, sorry im strugling to piece this together. what exactly does e2e with backend do? alsop where are doubleratchet.ts and x3dh.ts?
>
> so can I just tell my teamate to look at e2e with backend to basically know exactly what to do for the cpp client? just gotta be in cpp of course, and yes giv##o through the code and tell me about it
>
> give me a full commit message, i dont have postgres installed so I will get my teamate to test later, besides this is my crpyography part of the project complete?
>
> how long would it take for me to get the Postgres working on my Machine, am I betetr off spending 30 mins at this or at doing more work on the blockchain part?
>
> just to double check, looking back at the changes to common.py, are you confident these were all good correct changes? also why did you create wire_payloads im still unsure what the deal is with all of this "wire" stuff
>
> how about things like getting rid of a missing keys check, is this okay?

---

## 2. Blockchain

### Initial scaffold

> I need to build the Blockchain integrity module for our secure messaging app.
>
> Please scaffold a Hardhat (or Node.js) project with the following:
> 1. A Solidity smart contract named `MessageFidelity.sol`. It should map a conversation ID or message ID to a `keccak256` hash and a block timestamp. It needs a function to store a hash, and a function to retrieve a hash.
> 2. A deployment script to deploy this to the Sepolia testnet (using ethers.js or viem).
> 3. A simple, standalone web interface (HTML/JS or simple React) where a user can paste a message's text, calculate its keccak256 hash locally, fetch the expected hash from the smart contract, and display a green "Pass" or red "Fail" fidelity result.
>
> Ensure the smart contract is simple, gas-efficient, and well-commented.

### Brief / status / merkle

> what is the current status of my blockchain, what % is just AI slop, what do I need to do and how does it align with the rest of the project that now exists
>
> okay have a look at the brief again and all of the code and see what can stay the same and what needs to change for the perfect working blockchain to store history of messages on it
>
> I am strugling to read and grasp all of that, i have ownership of crypto and blockchain and need to get this blckchain working asap so help me with length of time goals. so as a new message is sent it uses kecack 256 to hash it and put it on a new blck in the blockchain as evidence this message happeend, a merkle route exists to confirm this?
>
> im confused here so like my job right now is basically give an API or function call or something to be called when messages get sent which hashes the message and places it as some sort of NFT on a smart contract maybe? that makes sense to me but maybe i am wrong or not following brief with this
>
> can i not make use of a merkle tree so that as more hashes are added they go on the tree but there isj ust 1 singular hash to prove all messages are on the blockchain?
>
> okay go code it up with the merkle tree and have it all exactly as i described, give me a little guide explaining what each file does and what is needed from me next

### Deploy / teammates

> remove alot of comments and just leave the odd one so it looks more human and not just AI generated. what is fidelity here, is this the fidelty company? I have 1 sepolia wallet made with 0.05 etj, how do i proceed
>
> so i have 1 wallet made with 0.05 sepolia in it, is this enough or do i need 2 wallets give me step by step
>
> so will there be individual merkle trees per chat or how does it work, also how does hosting work, do i need to get this running on the vm, does backend stuff need to happen or what? MESSAGE_FIDELITY_ADDRESS=0xYOUR_DEPLOYED_CONTRACT what do i do here so?
>
> so what does alchemy exactly do, serve APIs for my teamates while is the private key where the contract is deployed, i only just added fidelity address what is this, everything ran fine without it before i have it set as 0x925029Bab37aB27BE775A05524C58b619DE43899
>
> well if we have a .env file here does that not imply that we have to run the blockchain codel ocally so the client can call it down the line. I just want to have this set up and give a very simple guide to my teamate to get this integrated with cient or backend
>
> i got rid of the intergration doc, idont think it is needed just double checking that you are running kecack 256 so is this fully deployed now, the c++ is the client, are there basically just functions i can call that will do each thing, can i tell my teamate, here re the functions you need and the arguments and what they do, and there is nothing else they need to do because it is already hosted and deployed?
>
> i said to my teamate should i be running the blockchain on a vm instead of locally and having an API for the functions and he asked in reference to hosting it on vm "What specifically" but im not really sure what would even be running or if this makes sense to do
>
> so what does it look like for these functions to be called, the blockchain foler needs to be built right, just say this simply dont over complicate
>
> [Daniel] ++ client -> POST /api/v1/messages -> backend stores message and creates pending anchor
> Blockchain worker/script -> reads pending anchors -> calls Solidity storeHash(record_id, digest) -> gets transaction_hash -> updates blockchain_anchors status = confirmed
> C++ client -> GET /api/v1/messages/{message_id}/anchor -> displays pending/confirmed status
>
> what exactly is the blockhain worker / script? teamate sent this, what do i do, do i need a blockchain worker, do i have one?

---

## 3. Backend / VM / docker

> why is docker-compose.yml needed, i know docker has an image for the postgres environment but like how does this all work, is docker just a server or does the docker image need to be ran on the vm or what?
>
> just noticed that my teamate already set this up in the vm so u can probably delete all of my docker stuff
>
> I undid all docker stuff because I discorvered docker was already on the vm from my teamate, i do need to get the rest of the backend api stuff running on it tho, help me, this is my current state [terminal output on VM]
>
> only create stuff on the db if u are certain my teamate hasnt yet
>
> so should the backend and db all be running on the vm now, can I adapt my test code to ensure this and test it working
>
> the vm should be a long term living server so the backend runs 24/7 lets fix this and tell me what way t proceed given this info
>
> okay now let me do the full e2e test but it should be with the backend hosted on vm
>
> VM name: kfc, IP: 200.69.13.70, Username: student, Your specific SSH port: 2210 (team VM)
>
> are we supposed use ssh port 2210? that makes sense to me for API endpoints instead of our previous lcal host 8000
>
> E2E is a test right, so this shouldnt need to be ran off vm, the vm should give me an api end point that I can access to do what is needed, i should be able to access this api with the right url and run my tests locally
>
> curl http://200.69.13.70:8000/doc are u sure this is thr right command to test this are usure 2210 shouldnt be the endpoint or something, is there anything i can do to fix this networks issue, that is one of the modules for this subject
>
> see i think KFC needs to be in the url somewhere, there are various teams usig this vm, our name is KFC
>
> how do we know that no other team is using 8000, surley the odds of another team using 8000 is very high? or is KFC a unique vm and every other team has their own unique vm?
>
> KFC is within a vm called alderan but maybe it is its own unique sub vm? also can i close that wsl window and the backwnd will stay running?
>
> is there anything i can try do rn to access this from outside the vm?
>
> https://kfc.theburkenator.com/docs is should be avaiable here
>
> I want to try get the backend and db working now, my teamate mentioned The db is on docker it's already running as far as I know but i dont fully rememebr how this all works, also once it is all ready I need to try get it running on the VM
>
> @terminals explain what I AM EVEN trying to run this for then explain what the problem is and fix it, dont do anything crazy

---

## 4. Teammate / repo stuff

> @Epic-KFC-daniel-backend-db.zip this is my teamtes branch with the backend stuff, review it for us and let us know how it lines up with the stuff I have implemented, point out good and bad things
>
> okay put this all in a md file I can share with him
>
> rephrase the md folder to a guide on how to make it work with my crypto code
>
> init this repo https://github.com/EoinOKelly/Epic-KFC.git

---

## Outcomes (roughly)

| Area | What came out of it |
|------|---------------------|
| Cryptography | `cryptography/`, libsignal, wire format, e2e scripts, docs |
| Blockchain | Hardhat, merkle contract, sepolia, fidelity UI |
| Backend / VM | API on VM, systemd, kfc.theburkenator.com |
| Integration | backend-crypto docs, review md for daniel |
