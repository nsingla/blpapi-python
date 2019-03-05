# abstractsession.py

"""A common interface shared between publish and consumer sessions.

This file defines a class 'AbstractSession' - an interface which is shared
between its concrete implementations 'Session' and 'ProviderSession'.

SERVICE IDENTIFIER
------------------
A service identifier is the fully qualified service name which uniquely
identifies the service in the API infrastructure.  A service must be of the
form "//<namespace>/<service-name>" where '<namespace>' and '<local-name>' are
non-empty strings of characters from the set '[-_.a-zA-Z0-9]'. Service
identifiers are case-insensitive, but clients are encouraged to prefer
identifiers without upper-case characters.  Note that the <namespace> and
<service-name> cannot contain the character '/'.
"""


from . import exception
from .exception import _ExceptionUtil
from .identity import Identity
from .service import Service
from . import internals
from .internals import CorrelationId
from . import utils
from .compat import with_metaclass

@with_metaclass(utils.MetaClassForClassesWithEnums)
class AbstractSession(object):
    """A common interface shared between publish and consumer sessions.

    This class provides an abstract session which defines shared interface
    between publish and consumer requests for Bloomberg

    Sessions manage access to services either by requests and
    responses or subscriptions. A Session can dispatch events and
    replies in either a synchronous or asynchronous mode. The mode
    of a Session is determined when it is constructed and cannot be
    changed subsequently.

    A Session is asynchronous if an EventHandler object is
    supplied when it is constructed. The nextEvent() method may not be called.
    All incoming events are delivered to the EventHandler supplied on
    construction.

    If supplied, EventHandler is a callable object that takes two arguments:
    received event and related session.

    A Session is synchronous if an EventHandler object is not
    supplied when it is constructed. The nextEvent() method must be
    called to read incoming events.

    Several methods in Session take a CorrelationId parameter. The
    application may choose to supply its own CorrelationId values
    or allow the Session to create values. If the application
    supplies its own CorrelationId values it must manage their
    lifetime such that the same value is not reused for more than
    one operation at a time. The lifetime of a CorrelationId begins
    when it is supplied in a method invoked on a Session and ends
    either when it is explicitly cancelled using cancel() or
    unsubscribe(), when a RESPONSE Event (not a PARTIAL_RESPONSE)
    containing it is received or when a SUBSCRIPTION_STATUS Event
    which indicates that the subscription it refers to has been
    terminated is received.

    When using an asynchronous Session the application must be
    aware that because the callbacks are generated from another
    thread they may be processed before the call which generates
    them has returned. For example, the SESSION_STATUS Event
    generated by a startAsync() may be processed before
    startAsync() has returned (even though startAsync() itself will
    not block).

    This becomes more significant when Session generated
    CorrelationIds are in use. For example, if a call to
    subscribe() which returns a Session generated CorrelationId has
    not completed before the first Events which contain that
    CorrelationId arrive the application may not be able to
    interpret those events correctly. For this reason, it is
    preferable to use user generated CorrelationIds when using
    asynchronous Sessions. This issue does not arise when using a
    synchronous Session as long as the calls to subscribe() etc are
    made on the same thread as the calls to nextEvent().
    """

    def __init__(self, handle=None):
        """Instantiate an 'AbstractSession' with the specified handle.

        This function is for internal use only. Clients should create sessions
        using one of the concrete subclasses of 'AbstractSession'.

        """

        if self.__class__ is AbstractSession:
            raise NotImplementedError("Don't instantiate this class directly.\
 Create sessions using one of the concrete subclasses of this class.")
        self.__handle = handle

    def openService(self, serviceName):
        """Open the service identified by the specified 'serviceName'.

        Attempt to open the service identified by the specified
        'serviceName' and block until the service is either opened
        successfully or has failed to be opened. Return 'True' if
        the service is opened successfully and 'False' if the
        service cannot be successfully opened.

        The 'serviceName' must contain a fully qualified service name. That
        is, it must be of the form "//<namespace>/<service-name>".

        Before openService() returns a SERVICE_STATUS Event is
        generated. If this is an asynchronous Session then this
        Event may be processed by the registered EventHandler
        before openService() has returned.
        """
        return internals.blpapi_AbstractSession_openService(
            self.__handle,
            serviceName) == 0

    def openServiceAsync(self, serviceName, correlationId=None):
        """Begin the process to open the service and return immediately.

        Begin the process to open the service identified by the
        specified 'serviceName' and return immediately. The optional
        specified 'correlationId' is used to track Events generated
        as a result of this call. The actual correlationId which
        will identify Events generated as a result of this call is
        returned.

        The 'serviceName' must contain a fully qualified service name. That
        is, it must be of the form "//<namespace>/<service-name>".

        The application must monitor events for a SERVICE_STATUS
        Event which will be generated once the service has been
        successfully opened or the opening has failed.
        """
        if correlationId is None:
            correlationId = CorrelationId()
        _ExceptionUtil.raiseOnError(
            internals.blpapi_AbstractSession_openServiceAsync(
                self.__handle,
                serviceName,
                correlationId._handle()))
        return correlationId

    def sendAuthorizationRequest(self,
                                 request,
                                 identity,
                                 correlationId=None,
                                 eventQueue=None):
        """Send the specified 'authorizationRequest'.

        Send the specified 'authorizationRequest' and update the
        specified 'identity' with the results. If the optionally
        specified 'correlationId' is supplied, it is used; otherwise
        create a CorrelationId. The actual CorrelationId used is
        returned. If the optionally specified 'eventQueue' is
        supplied all Events relating to this Request will arrive on
        that EventQueue.

        The underlying user information must remain valid until the
        Request has completed successfully or failed.

        A successful request will generate zero or more
        PARTIAL_RESPONSE Messages followed by exactly one RESPONSE
        Message. Once the final RESPONSE Message has been received
        the specified 'identity' will have been updated to contain
        the users entitlement information and the CorrelationId
        associated with the request may be re-used. If the request
        fails at any stage a REQUEST_STATUS will be generated, the
        specified 'identity' will not be modified and the
        CorrelationId may be re-used.

        The 'identity' supplied must have been returned from this
        Session's createIdentity() method.

        """

        if correlationId is None:
            correlationId = CorrelationId()
        _ExceptionUtil.raiseOnError(
            internals.blpapi_AbstractSession_sendAuthorizationRequest(
                self.__handle,
                request._handle(),
                identity._handle(),
                correlationId._handle(),
                None if eventQueue is None else eventQueue._handle(),
                None,  # no request label
                0))    # request label length 0
        if eventQueue is not None:
            eventQueue._registerSession(self)
        return correlationId

    def cancel(self, correlationId):
        """Cancel 'correlationId' request.

        If the specified 'correlationId' identifies a current
        request then cancel that request.

        Once this call returns the specified 'correlationId' will
        not be seen in any subsequent Message obtained from a
        MessageIterator by calling next(). However, any Message
        currently pointed to by a MessageIterator when
        cancel() is called is not affected even if it has the
        specified 'correlationId'. Also any Message where a
        reference has been retained by the application may still
        contain the 'correlationId'. For these reasons, although
        technically an application is free to re-use
        'correlationId' as soon as this method returns it is
        preferable not to aggressively re-use correlation IDs,
        particularly with an asynchronous Session.

        'correlationId' should be either a correlation Id or a list of
        correlation Ids.

        """

        _ExceptionUtil.raiseOnError(internals.blpapi_AbstractSession_cancel(
            self.__handle,
            correlationId._handle(),
            1,     # number of correlation IDs supplied
            None,  # no request label
            0))    # request label length 0

    def generateToken(self, correlationId=None,
                      eventQueue=None, authId=None, ipAddress=None):
        """Generate a token to be used for authorization.

        The 'authId' and 'ipAddress' must be provided together and can only be
        provided if the authentication mode is 'MANUAL'.

        Raises 'InvalidArgumentException' if the authentication options in
        'SessionOptions' or the arguments to the function are invalid.
        """
        if correlationId is None:
            correlationId = CorrelationId()

        if authId is None and ipAddress is None:
            _ExceptionUtil.raiseOnError(
                internals.blpapi_AbstractSession_generateToken(
                    self.__handle,
                    correlationId._handle(),
                    None if eventQueue is None else eventQueue._handle()))
        elif authId is not None and ipAddress is not None:
            _ExceptionUtil.raiseOnError(
                internals.blpapi_AbstractSession_generateManualToken(
                    self.__handle,
                    correlationId._handle(),
                    authId,
                    ipAddress,
                    None if eventQueue is None else eventQueue._handle()))
        else:
            raise exception.InvalidArgumentException(
                    "'authId' and 'ipAddress' must be provided together", 0)
        if eventQueue is not None:
            eventQueue._registerSession(self)
        return correlationId

    def getService(self, serviceName):
        """Return a Service object representing the service.

        Return a Service object representing the service identified by the
        specified 'serviceName'.

        The 'serviceName' must contain a fully qualified service name. That
        is, it must be of the form "//<namespace>/<service-name>".

        If the service identified by the specified 'serviceName' is not open
        already then an InvalidStateException is raised.
        """
        errorCode, service = internals.blpapi_AbstractSession_getService(
            self.__handle,
            serviceName)
        _ExceptionUtil.raiseOnError(errorCode)
        return Service(service, self)

    def createIdentity(self):
        """Return a Identity which is valid but has not been authorized."""
        return Identity(
            internals.blpapi_AbstractSession_createIdentity(self.__handle),
            self)

    # Protect enumeration constant(s) defined in this class and in classes
    # derived from this class from changes:
    
__copyright__ = """
Copyright 2012. Bloomberg Finance L.P.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to
deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:  The above
copyright notice and this permission notice shall be included in all copies
or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
IN THE SOFTWARE.
"""
