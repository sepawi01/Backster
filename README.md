# Backster

Backster är Parks and Resorts interna chatt bot. Backster är byggd med hjälp av
AzureOpenAI & Langgraph/Langchain (https://www.langchain.com/langgraph) och 
hjälper medarbetare på Parks and Resorts med att svara på arbetsrelaterade frågor.
Och kan också exekvera några enklare uppgifter.

## Utveckling
Applikationen består av två delar, en backend och en frontend. Backend är skriven i Python och frontend i React.

### Frontend
Frontenden kan köras lokalt genom att installera de nödvändiga paketen med hjälp av npm install.
Det är backend som servar frontenden så om förändringar görs i frontenden så är det rekommenderat 
att bygga om frontenden (npm build) och starta om backenden. Istället för att köra npm run dev.
Inget mer än att bygga frontend är nödvändigt för att backend ska kunna serva den.
Backend använde de filer som ligger i frontend/dist mappen. 

### Backend
Backenden kan köras lokalt via att sätta upp en python miljö och installera de nödvändiga paketen 
med hjälp av Pipfile och pipenv. Alternativt starta och spinna upp en docker container.

**.env fil** \
För att köra backenden så krävs det en .env fil som innehåller de variabler som kan hittas i .env.example filen.
Om du kör applikationen med docker så kan du starta upp containern med nödvändiga variabler genom att köra
`docker build -t backster .` och `docker run --env-file .env -p 8000:8000 backster`

## Deployment
Applikationen är deployad i Azure och körs i en App Service som är kopplad till en Azure Container Registry.
För att deploya en ny version av applikationen så behöver en ny docker image byggas och pushas till Azure Container Registry.
Därefter behöver App Service startas om. 

För att bygga och deploya en ny version av applikationen så kan du köra de olika skripten i 
docker-scripts.sh. Kör dom rad för rad för att bygga och pusha en ny version av applikationen. 


